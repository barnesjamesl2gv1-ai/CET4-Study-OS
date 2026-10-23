"""Loopback-only API and bundled static frontend."""

from __future__ import annotations

import os
import json
import sqlite3
import zipfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.db import connect, data_dir
from backend.imports import create_paper, import_question, list_assets, save_asset
from backend.audio import confirm as confirm_audio_segment, segments as list_segments, suggestions as audio_suggestions
from backend.practice import save_answer, save_position, session as get_practice_session, start as start_practice
from backend.backups import backup, daily_if_needed, restore, verify

@asynccontextmanager
async def lifespan(application: FastAPI):
    daily_if_needed()
    yield


app = FastAPI(title="CET-4 Study OS", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.middleware("http")
async def local_request_guard(request: Request, call_next):
    host = request.url.hostname
    if host not in {"127.0.0.1", "localhost", "testserver"}:
        return JSONResponse({"detail": "仅允许本机访问"}, status_code=403)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        parsed = urlparse(origin or "")
        if parsed.hostname != host or parsed.port != request.url.port:
            return JSONResponse({"detail": "跨站请求被拒绝"}, status_code=403)
    return await call_next(request)


@app.get("/healthz")
def healthz():
    with connect() as db:
        db.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.get("/api/papers")
def list_papers():
    with connect() as db:
        rows = db.execute("SELECT id,year,session_month,set_number,status FROM papers ORDER BY year DESC,session_month DESC,set_number").fetchall()
    return [dict(row) for row in rows]


class NewPaper(BaseModel):
    year: int
    session_month: int
    set_number: int


class ReviewedQuestion(BaseModel):
    number: int
    kind: str
    prompt: str = ""
    passage_text: str = ""
    options: list[str] = Field(default_factory=list)
    answer: str | None = None
    rationale: str = ""
    confirmed: bool = False
    existing_question_id: str | None = None


@app.post("/api/papers")
def new_paper(paper: NewPaper):
    return create_paper(paper.year, paper.session_month, paper.set_number)


@app.get("/api/papers/{paper_id}/assets")
def paper_assets(paper_id: str):
    return list_assets(paper_id)


@app.get("/api/papers/{paper_id}/import-status")
def import_status(paper_id: str):
    with connect() as db:
        if not db.execute("SELECT 1 FROM papers WHERE id=?", (paper_id,)).fetchone():
            raise HTTPException(404, "试卷不存在")
        counts = {row["role"]: row["count"] for row in db.execute(
            "SELECT role,COUNT(*) count FROM source_assets WHERE paper_id=? AND verification_status!='invalid' GROUP BY role", (paper_id,))}
        invalid = db.execute("SELECT COUNT(*) FROM source_assets WHERE paper_id=? AND verification_status='invalid'", (paper_id,)).fetchone()[0]
        questions = db.execute("SELECT COUNT(*) FROM questions WHERE paper_id=? AND lifecycle='ready'", (paper_id,)).fetchone()[0]
    issues = [f"缺少{label}" for role, label in (("paper", "试卷"), ("audio", "听力音频"), ("answer", "答案解析")) if not counts.get(role)]
    if invalid:
        issues.append(f"{invalid} 个无效文件")
    if not questions:
        issues.append("尚无人工核对题目")
    return {"issues": issues, "verified_questions": questions, "mock_ready": False,
            "note": "必须人工核对完整题目、答案及音频；当前版本不提供正式模考"}


@app.post("/api/papers/{paper_id}/assets")
async def upload_asset(paper_id: str, role: str = Form(...), file: UploadFile = File(...)):
    return await save_asset(paper_id, role, file)


@app.get("/api/assets/{asset_id}")
def download_asset(asset_id: str):
    with connect() as db:
        row = db.execute("SELECT relative_path,original_filename,role FROM source_assets WHERE id=?", (asset_id,)).fetchone()
    if not row:
        raise HTTPException(404, "文件不存在")
    root = data_dir().resolve()
    target = (root / row["relative_path"]).resolve()
    if not target.is_relative_to(root / "assets") or not target.is_file():
        raise HTTPException(404, "文件不存在")
    if row["role"] == "audio":
        return FileResponse(target, media_type="audio/mpeg", content_disposition_type="inline")
    return FileResponse(target, filename=row["original_filename"])


class SegmentConfirmation(BaseModel):
    start_ms: int
    end_ms: int
    question_numbers: list[int]


@app.get("/api/assets/{asset_id}/segment-suggestions")
def segment_suggestions(asset_id: str):
    return audio_suggestions(asset_id)


@app.post("/api/assets/{asset_id}/segments")
def confirm_segment(asset_id: str, segment: SegmentConfirmation):
    return confirm_audio_segment(asset_id, segment.start_ms, segment.end_ms, segment.question_numbers)


@app.get("/api/papers/{paper_id}/segments")
def paper_segments(paper_id: str):
    return list_segments(paper_id)


class NewPractice(BaseModel):
    paper_id: str
    section: str


class Answer(BaseModel):
    selected: str


@app.post("/api/practice/sessions")
def new_practice(request: NewPractice):
    return start_practice(request.paper_id, request.section)


@app.get("/api/practice/sessions/{session_id}")
def practice_session(session_id: str):
    return get_practice_session(session_id)


@app.put("/api/practice/sessions/{session_id}/answers/{question_id}")
def practice_answer(session_id: str, question_id: str, answer: Answer):
    return save_answer(session_id, question_id, answer.selected)


@app.put("/api/practice/sessions/{session_id}/position/{question_id}")
def practice_position(session_id: str, question_id: str):
    return save_position(session_id, question_id)


@app.get("/api/papers/{paper_id}/practice-sessions")
def practice_sessions(paper_id: str):
    with connect() as db:
        rows = db.execute("SELECT id,section,updated_at FROM practice_sessions WHERE paper_id=? ORDER BY updated_at DESC", (paper_id,)).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/backups")
def list_backups():
    with connect() as db:
        rows = db.execute("SELECT id,created_at,backup_kind,relative_path,verified FROM backup_records ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/backups")
def create_backup():
    return backup("manual")


@app.get("/api/backups/{backup_id}/export")
def export_backup(backup_id: str):
    with connect() as db:
        row = db.execute("SELECT relative_path FROM backup_records WHERE id=?", (backup_id,)).fetchone()
    if not row:
        raise HTTPException(404, "备份不存在")
    root = data_dir().resolve()
    target = (root / row["relative_path"]).resolve()
    if not target.is_relative_to(root / "backups") or not target.is_file():
        raise HTTPException(404, "备份文件不存在")
    return FileResponse(target, filename=target.name, media_type="application/zip")


@app.post("/api/backups/restore")
async def restore_backup(file: UploadFile = File(...), confirmed: bool = Form(False)):
    if not confirmed:
        raise HTTPException(422, "请先确认恢复操作")
    root = data_dir()
    folder = root / "backups"
    folder.mkdir(exist_ok=True)
    path = folder / f"imported-{uuid.uuid4()}.zip"
    size = 0
    try:
        with path.open("wb") as stream:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 1024 * 1024 * 1024:
                    raise HTTPException(413, "备份超过 1 GB 限制")
                stream.write(chunk)
        try:
            verify(path)
            return restore(path)
        except (ValueError, OSError, sqlite3.DatabaseError, zipfile.BadZipFile) as error:
            raise HTTPException(422, f"备份恢复失败：{error}") from error
    finally:
        if not size:
            path.unlink(missing_ok=True)


@app.post("/api/papers/{paper_id}/questions")
def add_reviewed_question(paper_id: str, question: ReviewedQuestion):
    return import_question(paper_id, question.model_dump())


@app.get("/api/papers/{paper_id}/questions")
def paper_questions(paper_id: str):
    with connect() as db:
        rows = db.execute("""SELECT q.id,q.ordinal,q.question_kind,p.body_text passage_text,v.version_no,v.prompt_text,
            v.options_json,v.correct_answer_json,v.rationale_text FROM questions q
            LEFT JOIN passages p ON p.id=q.passage_id
            JOIN question_versions v ON v.question_id=q.id
            WHERE q.paper_id=? AND v.version_no=(SELECT MAX(version_no) FROM question_versions WHERE question_id=q.id)
            ORDER BY q.ordinal""", (paper_id,)).fetchall()
    return [{"id": row["id"], "number": row["ordinal"], "kind": row["question_kind"],
             "version": row["version_no"], "prompt": row["prompt_text"], "passage_text": row["passage_text"] or "",
             "options": json.loads(row["options_json"]),
             "answer": json.loads(row["correct_answer_json"]),
             "rationale": row["rationale_text"]} for row in rows]


@app.get("/{full_path:path}")
def frontend(full_path: str):
    dist = Path(os.environ.get("CET4_FRONTEND_DIST") or Path(__file__).resolve().parents[1] / "frontend" / "dist")
    target = (dist / full_path).resolve()
    if full_path and target.is_relative_to(dist.resolve()) and target.is_file():
        return FileResponse(target)
    index = dist / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(404, "前端尚未构建")
