"""Audio suggestions and explicit segment confirmation."""

from __future__ import annotations

import uuid

from fastapi import HTTPException

from backend.db import connect, data_dir
from backend.m0_review import confirm_segment, suggest_segments


def audio_asset(asset_id: str):
    with connect() as db:
        row = db.execute("SELECT * FROM source_assets WHERE id=? AND role='audio'", (asset_id,)).fetchone()
    if not row or not row["duration_ms"]:
        raise HTTPException(404, "音频不存在或时长未验证")
    return dict(row)


def suggestions(asset_id: str) -> list[dict]:
    asset = audio_asset(asset_id)
    path = data_dir() / asset["relative_path"]
    try:
        proposed = suggest_segments(path, asset["duration_ms"])
    except ValueError:
        proposed = []
    return proposed or [{"start_ms": 0, "end_ms": asset["duration_ms"], "confirmation": "pending"}]


def confirm(asset_id: str, start_ms: int, end_ms: int, question_numbers: list[int]) -> dict:
    asset = audio_asset(asset_id)
    try:
        segment = confirm_segment(start_ms, end_ms, asset["duration_ms"], question_numbers)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    with connect() as db:
        placeholders = ",".join("?" for _ in segment["question_numbers"])
        rows = db.execute(f"SELECT id,ordinal,question_kind FROM questions WHERE paper_id=? AND ordinal IN ({placeholders})",
                          (asset["paper_id"], *segment["question_numbers"])).fetchall()
        if len(rows) != len(segment["question_numbers"]) or any(not row["question_kind"].startswith("listening_") for row in rows):
            raise HTTPException(422, "片段题号必须属于同套已核对听力题")
        segment_id = str(uuid.uuid4())
        db.execute("INSERT INTO audio_segments(id,asset_id,start_ms,end_ms,confirmation) VALUES(?,?,?,?,?)",
                   (segment_id, asset_id, start_ms, end_ms, "confirmed"))
        for row in rows:
            db.execute("INSERT INTO question_audio_segments(question_id,segment_id) VALUES(?,?)", (row["id"], segment_id))
    return {"id": segment_id, **segment}


def segments(paper_id: str) -> list[dict]:
    with connect() as db:
        rows = db.execute("""SELECT s.id,s.asset_id,s.start_ms,s.end_ms,q.ordinal
            FROM audio_segments s JOIN source_assets a ON a.id=s.asset_id
            JOIN question_audio_segments m ON m.segment_id=s.id
            JOIN questions q ON q.id=m.question_id
            WHERE a.paper_id=? AND s.confirmation='confirmed' ORDER BY q.ordinal""", (paper_id,)).fetchall()
    return [dict(row) for row in rows]
