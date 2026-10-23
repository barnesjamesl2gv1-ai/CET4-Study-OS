import io
import zipfile

from fastapi.testclient import TestClient

from backend.app import app

ORIGIN = {"origin": "http://testserver"}


def docx_bytes():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="x"><w:t>Question 1</w:t></w:document>')
    return stream.getvalue()


def test_upload_duplicate_and_missing_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("CET4_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    response = client.post("/api/papers", json={"year": 2025, "session_month": 12, "set_number": 1}, headers=ORIGIN)
    assert response.status_code == 200
    paper = response.json()
    assert client.post("/api/papers", json={"year": 2025, "session_month": 12, "set_number": 1}, headers=ORIGIN).status_code == 409
    url = f"/api/papers/{paper['id']}/assets"
    assert "缺少试卷" in client.get(f"/api/papers/{paper['id']}/import-status").json()["issues"]
    uploaded = client.post(url, data={"role": "paper"}, files={"file": ("paper.docx", docx_bytes())}, headers=ORIGIN)
    assert uploaded.status_code == 200
    asset = uploaded.json()
    assert asset["status"] == "needs_review"
    assert client.get(url).json()[0]["id"] == asset["id"]
    assert client.get(f"/api/assets/{asset['id']}").content == docx_bytes()
    assert client.post(url, data={"role": "paper"}, files={"file": ("paper.docx", docx_bytes())}, headers=ORIGIN).status_code == 409
    assert client.post(url, data={"role": "audio"}, files={"file": ("fake.mp3", b"fake")}, headers=ORIGIN).status_code == 422
    assert len(client.get(url).json()) == 1
    assert "缺少听力音频" in client.get(f"/api/papers/{paper['id']}/import-status").json()["issues"]


def test_question_revision_preserves_old_version(tmp_path, monkeypatch):
    monkeypatch.setenv("CET4_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    paper_id = client.post("/api/papers", json={"year": 2024, "session_month": 6, "set_number": 2}, headers=ORIGIN).json()["id"]
    url = f"/api/papers/{paper_id}/questions"
    question = {"number": 1, "kind": "careful", "prompt": "Question", "options": ["A", "B"], "answer": "A", "confirmed": True}
    first = client.post(url, json=question, headers=ORIGIN).json()
    assert first["version"] == 1
    assert client.post(url, json={**question, "answer": "B"}, headers=ORIGIN).status_code == 409
    second = client.post(url, json={**question, "answer": "B", "existing_question_id": first["id"]}, headers=ORIGIN)
    assert second.json()["version"] == 2
    assert client.get(url).json()[0]["answer"] == "B"
    from backend.db import connect
    with connect() as db:
        answers = [row[0] for row in db.execute("SELECT correct_answer_json FROM question_versions WHERE question_id=? ORDER BY version_no", (first["id"],))]
    assert answers == ['"A"', '"B"']
