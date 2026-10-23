"""Daily practice persistence. No score is calculated."""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException

from backend.db import connect
from backend.imports import now


def start(paper_id: str, section: str) -> dict:
    if section not in ("listening", "reading"):
        raise HTTPException(422, "训练类别无效")
    session_id = str(uuid.uuid4())
    with connect() as db:
        if not db.execute("SELECT 1 FROM papers WHERE id=?", (paper_id,)).fetchone():
            raise HTTPException(404, "试卷不存在")
        db.execute("INSERT INTO practice_sessions(id,paper_id,section,state,started_at,updated_at) VALUES(?,?,?,?,?,?)",
                   (session_id, paper_id, section, "in_progress", now(), now()))
    return {"id": session_id, "paper_id": paper_id, "section": section}


def session(session_id: str) -> dict:
    with connect() as db:
        row = db.execute("SELECT * FROM practice_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(404, "训练记录不存在")
        answers = db.execute("SELECT q.ordinal,a.selected_answer_json FROM practice_answers a JOIN questions q ON q.id=a.question_id WHERE a.practice_session_id=?", (session_id,)).fetchall()
    return {"id": row["id"], "paper_id": row["paper_id"], "section": row["section"],
            "last_question_id": row["last_question_id"], "answers": {str(a["ordinal"]): json.loads(a["selected_answer_json"]) for a in answers}}


def save_answer(session_id: str, question_id: str, answer: str) -> dict:
    with connect() as db:
        state = db.execute("SELECT paper_id,section,state FROM practice_sessions WHERE id=?", (session_id,)).fetchone()
        if not state or state["state"] != "in_progress":
            raise HTTPException(404, "训练记录不可写")
        question = db.execute("SELECT paper_id,question_kind FROM questions WHERE id=? AND lifecycle='ready'", (question_id,)).fetchone()
        if not question or question["paper_id"] != state["paper_id"]:
            raise HTTPException(422, "题目不属于本次训练")
        if (state["section"] == "reading") != (question["question_kind"] in ("cloze", "matching", "careful")):
            raise HTTPException(422, "题型与训练类别不匹配")
        version = db.execute("SELECT id,options_json FROM question_versions WHERE question_id=? ORDER BY version_no DESC LIMIT 1", (question_id,)).fetchone()
        options = json.loads(version["options_json"])
        if options and answer not in options:
            raise HTTPException(422, "选项无效")
        if question["question_kind"] == "cloze":
            existing = db.execute("""SELECT 1 FROM practice_answers a JOIN questions q ON q.id=a.question_id
                WHERE a.practice_session_id=? AND a.question_id!=? AND q.question_kind='cloze' AND a.selected_answer_json=?""",
                (session_id, question_id, json.dumps(answer, ensure_ascii=False))).fetchone()
            if existing:
                raise HTTPException(409, "该单词已用于其他空格")
        db.execute("""INSERT INTO practice_answers(practice_session_id,question_id,question_version_id,selected_answer_json,saved_at)
            VALUES(?,?,?,?,?) ON CONFLICT(practice_session_id,question_id) DO UPDATE SET
            question_version_id=excluded.question_version_id,selected_answer_json=excluded.selected_answer_json,saved_at=excluded.saved_at""",
            (session_id, question_id, version["id"], json.dumps(answer, ensure_ascii=False), now()))
        db.execute("UPDATE practice_sessions SET last_question_id=?,updated_at=? WHERE id=?", (question_id, now(), session_id))
    return {"saved": True, "answer": answer}


def save_position(session_id: str, question_id: str) -> dict:
    with connect() as db:
        row = db.execute("SELECT paper_id FROM practice_sessions WHERE id=? AND state='in_progress'", (session_id,)).fetchone()
        if not row or not db.execute("SELECT 1 FROM questions WHERE id=? AND paper_id=?", (question_id, row["paper_id"])).fetchone():
            raise HTTPException(422, "训练记录或题目无效")
        db.execute("UPDATE practice_sessions SET last_question_id=?,updated_at=? WHERE id=?", (question_id, now(), session_id))
        db.execute("INSERT INTO practice_events(practice_session_id,event_type,question_id,occurred_at) VALUES(?,?,?,?)",
                   (session_id, "navigate", question_id, now()))
    return {"saved": True, "question_id": question_id}
