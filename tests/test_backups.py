import io
import sqlite3
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.backups import verify
from backend.backups import daily_if_needed

ORIGIN = {"origin": "http://testserver"}


def sample_docx():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="x"><w:t>Question</w:t></w:document>')
    return stream.getvalue()


def test_backup_restore_keeps_files_and_rolls_back_answers(tmp_path, monkeypatch):
    monkeypatch.setenv("CET4_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    source_bytes = sample_docx()
    paper = client.post("/api/papers", headers=ORIGIN,
                        json={"year": 2025, "session_month": 6, "set_number": 1}).json()["id"]
    asset = client.post(f"/api/papers/{paper}/assets", headers=ORIGIN, data={"role": "paper"},
                        files={"file": ("sample.docx", source_bytes)}).json()["id"]
    url = f"/api/papers/{paper}/questions"
    question = {"number": 1, "kind": "careful", "prompt": "Q", "options": ["A", "B"], "answer": "A", "confirmed": True}
    original = client.post(url, headers=ORIGIN, json=question).json()
    session = client.post("/api/practice/sessions", headers=ORIGIN,
                          json={"paper_id": paper, "section": "reading"}).json()["id"]
    answer_url = f"/api/practice/sessions/{session}/answers/{original['id']}"
    assert client.put(answer_url, headers=ORIGIN, json={"selected": "A"}).status_code == 200
    created = client.post("/api/backups", headers=ORIGIN)
    assert created.status_code == 200, created.text
    backup = created.json()
    assert verify(Path(backup["path"]))["version"] == 1
    exported = client.get(f"/api/backups/{backup['id']}/export").content
    client.put(answer_url, headers=ORIGIN, json={"selected": "B"})
    assert client.get(f"/api/practice/sessions/{session}").json()["answers"]["1"] == "B"
    restored = client.post("/api/backups/restore", headers=ORIGIN,
                           data={"confirmed": "true"}, files={"file": ("backup.zip", exported)})
    assert restored.status_code == 200, restored.text
    assert Path(restored.json()["pre_restore_backup"]).is_file()
    assert client.get(f"/api/practice/sessions/{session}").json()["answers"]["1"] == "A"
    assert client.get(f"/api/assets/{asset}").content == source_bytes
    with sqlite3.connect(tmp_path / "study.sqlite3") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_corrupt_backup_rejected_without_mutating_database(tmp_path, monkeypatch):
    monkeypatch.setenv("CET4_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    client.post("/api/papers", headers=ORIGIN, json={"year": 2026, "session_month": 12, "set_number": 1})
    before = client.get("/api/papers").json()
    result = client.post("/api/backups/restore", headers=ORIGIN,
                         data={"confirmed": "true"}, files={"file": ("bad.zip", b"not a zip")})
    assert result.status_code == 422
    assert client.get("/api/papers").json() == before


def test_daily_backup_runs_once_and_tampered_manifest_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("CET4_DATA_DIR", str(tmp_path))
    first = daily_if_needed()
    assert first and Path(first["path"]).is_file()
    assert daily_if_needed() is None
    forged = tmp_path / "forged.zip"
    with zipfile.ZipFile(first["path"]) as original, zipfile.ZipFile(forged, "w") as modified:
        for name in original.namelist():
            content = original.read(name)
            modified.writestr(name, content + b"bad" if name == "database.sqlite3" else content)
    import pytest
    with pytest.raises(ValueError):
        verify(forged)
    with sqlite3.connect(tmp_path / "study.sqlite3") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
