from fastapi.testclient import TestClient

from backend.app import app
from backend.db import connect, initialize


def test_database_persists_and_enforces_foreign_keys(tmp_path):
    path = tmp_path / "study.sqlite3"
    initialize(path)
    with connect(path) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        db.execute("INSERT INTO papers VALUES(?,?,?,?,?,?,?)", ("p", 2026, 12, 1, "draft", "t", "t"))
    with connect(path) as db:
        assert db.execute("SELECT id FROM papers").fetchone()[0] == "p"


def test_health_and_origin_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("CET4_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/papers").json() == []
    assert "CET-4 Study OS" in client.get("/").text
    assert client.post("/api/papers", headers={"origin": "https://evil.example"}).status_code == 403
