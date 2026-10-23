from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app

ORIGIN = {"origin": "http://testserver"}
FIXTURE = Path(__file__).parent / "fixtures" / "synthetic-tone.mp3"


def new_paper(client):
    return client.post("/api/papers", json={"year": 2026, "session_month": 12, "set_number": 1}, headers=ORIGIN).json()["id"]


def add_question(client, paper_id, number, kind, options):
    return client.post(f"/api/papers/{paper_id}/questions", headers=ORIGIN,
                       json={"number": number, "kind": kind, "prompt": f"Q{number}",
                             "options": options, "answer": options[0], "confirmed": True}).json()["id"]


def test_confirmed_audio_segment_and_invalid_bounds(tmp_path, monkeypatch):
    monkeypatch.setenv("CET4_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    paper = new_paper(client)
    add_question(client, paper, 1, "listening_news", ["A", "B"])
    response = client.post(f"/api/papers/{paper}/assets", headers=ORIGIN,
                           data={"role": "audio"}, files={"file": ("sample.mp3", FIXTURE.read_bytes())})
    assert response.status_code == 200, response.text
    asset_id = response.json()["id"]
    assert client.get(f"/api/assets/{asset_id}").headers["content-type"].startswith("audio/mpeg")
    proposals = client.get(f"/api/assets/{asset_id}/segment-suggestions").json()
    assert proposals and proposals[0]["confirmation"] == "pending"
    invalid = client.post(f"/api/assets/{asset_id}/segments", headers=ORIGIN,
                          json={"start_ms": 0, "end_ms": 999999, "question_numbers": [1]})
    assert invalid.status_code == 422
    confirmed = client.post(f"/api/assets/{asset_id}/segments", headers=ORIGIN,
                            json={"start_ms": 0, "end_ms": 1000, "question_numbers": [1]})
    assert confirmed.status_code == 200
    assert client.get(f"/api/papers/{paper}/segments").json()[0]["ordinal"] == 1


def test_reading_autosave_uniqueness_and_matching_repeat(tmp_path, monkeypatch):
    monkeypatch.setenv("CET4_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    paper = new_paper(client)
    first = add_question(client, paper, 1, "cloze", ["word", "other"])
    second = add_question(client, paper, 2, "cloze", ["word", "other"])
    match1 = add_question(client, paper, 3, "matching", ["A", "B"])
    match2 = add_question(client, paper, 4, "matching", ["A", "B"])
    session_id = client.post("/api/practice/sessions", headers=ORIGIN,
                             json={"paper_id": paper, "section": "reading"}).json()["id"]
    def save(question, selected):
        return client.put(f"/api/practice/sessions/{session_id}/answers/{question}",
                          headers=ORIGIN, json={"selected": selected})
    assert save(first, "word").json()["saved"] is True
    assert save(second, "word").status_code == 409
    assert save(first, "other").status_code == 200
    assert save(second, "word").status_code == 200
    assert save(match1, "A").status_code == 200
    assert save(match2, "A").status_code == 200
    assert client.put(f"/api/practice/sessions/{session_id}/position/{first}", headers=ORIGIN).json()["saved"] is True
    reopened = TestClient(app).get(f"/api/practice/sessions/{session_id}").json()
    assert reopened["answers"] == {"1": "other", "2": "word", "3": "A", "4": "A"}
    assert reopened["last_question_id"] == first
