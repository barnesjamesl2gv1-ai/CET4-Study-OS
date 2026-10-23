"""Loopback-only API and bundled static frontend."""

from __future__ import annotations

import os
import json
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.db import connect, data_dir
from backend.imports import create_paper, import_question, list_assets, save_asset

app = FastAPI(title="CET-4 Study OS", docs_url=None, redoc_url=None)


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
        row = db.execute("SELECT relative_path,original_filename FROM source_assets WHERE id=?", (asset_id,)).fetchone()
    if not row:
        raise HTTPException(404, "文件不存在")
    root = data_dir().resolve()
    target = (root / row["relative_path"]).resolve()
    if not target.is_relative_to(root / "assets") or not target.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(target, filename=row["original_filename"])


@app.post("/api/papers/{paper_id}/questions")
def add_reviewed_question(paper_id: str, question: ReviewedQuestion):
    return import_question(paper_id, question.model_dump())


@app.get("/api/papers/{paper_id}/questions")
def paper_questions(paper_id: str):
    with connect() as db:
        rows = db.execute("""SELECT q.id,q.ordinal,q.question_kind,v.version_no,v.prompt_text,
            v.options_json,v.correct_answer_json,v.rationale_text FROM questions q
            JOIN question_versions v ON v.question_id=q.id
            WHERE q.paper_id=? AND v.version_no=(SELECT MAX(version_no) FROM question_versions WHERE question_id=q.id)
            ORDER BY q.ordinal""", (paper_id,)).fetchall()
    return [{"id": row["id"], "number": row["ordinal"], "kind": row["question_kind"],
             "version": row["version_no"], "prompt": row["prompt_text"],
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
