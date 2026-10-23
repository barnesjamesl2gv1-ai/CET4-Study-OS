"""Conservative source storage and manual question versioning."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend.db import connect, data_dir
from backend.m0_inspect import FORMATS, inspect_file, sniff

MAX_BYTES = 50 * 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_paper(year: int, month: int, set_number: int) -> dict:
    if not 2000 <= year <= 2100 or month not in (6, 12) or set_number < 1:
        raise HTTPException(422, "试卷年份、月份或套数无效")
    paper_id = str(uuid.uuid4())
    try:
        with connect() as db:
            db.execute("INSERT INTO papers VALUES(?,?,?,?,?,?,?)",
                       (paper_id, year, month, set_number, "draft", now(), now()))
    except sqlite3.IntegrityError as error:
        raise HTTPException(409, "该年份、月份和套数已存在") from error
    return {"id": paper_id, "year": year, "session_month": month, "set_number": set_number, "status": "draft"}


async def save_asset(paper_id: str, role: str, upload: UploadFile) -> dict:
    if role not in ("paper", "answer", "audio"):
        raise HTTPException(422, "文件类别无效")
    with connect() as db:
        if not db.execute("SELECT 1 FROM papers WHERE id=?", (paper_id,)).fetchone():
            raise HTTPException(404, "试卷不存在")
    filename = Path(upload.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in FORMATS or (role == "audio") != (suffix == ".mp3"):
        raise HTTPException(422, "文件格式与类别不匹配；旧式 DOC 请先转为 DOCX")
    root = data_dir()
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=assets, suffix=suffix, delete=False) as stream:
        temporary = Path(stream.name)
        digest = hashlib.sha256()
        size = 0
        try:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "文件超过 50 MB 限制")
                digest.update(chunk)
                stream.write(chunk)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if not size or sniff(temporary) != FORMATS[suffix]:
            raise HTTPException(422, "文件内容无效或与扩展名不一致")
        fingerprint = digest.hexdigest()
        with connect() as db:
            duplicate = db.execute("SELECT id FROM source_assets WHERE paper_id=? AND role=? AND sha256=?",
                                   (paper_id, role, fingerprint)).fetchone()
            if duplicate:
                raise HTTPException(409, "该试卷此类别已上传相同文件")
        final = assets / f"{fingerprint}{suffix}"
        if final.exists() and hashlib.sha256(final.read_bytes()).hexdigest() != fingerprint:
            raise HTTPException(500, "存储文件哈希冲突")
        if not final.exists():
            os.replace(temporary, final)
        report = inspect_file(final)
        asset_id = str(uuid.uuid4())
        with connect() as db:
            db.execute("INSERT INTO source_assets(id,paper_id,role,original_filename,relative_path,sha256,file_format,byte_size,verification_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (asset_id, paper_id, role, filename, str(final.relative_to(root)), fingerprint,
                        report["format"], size, "invalid" if report["status"] == "invalid" else "pending", now()))
        return {"id": asset_id, "role": role, "filename": filename, "sha256": fingerprint,
                "status": report["status"], "details": report["details"]}
    finally:
        temporary.unlink(missing_ok=True)


def list_assets(paper_id: str) -> list[dict]:
    with connect() as db:
        rows = db.execute("SELECT id,role,original_filename,sha256,verification_status,byte_size FROM source_assets WHERE paper_id=? ORDER BY created_at,id", (paper_id,)).fetchall()
    return [dict(row) for row in rows]


def import_question(paper_id: str, question: dict) -> dict:
    """Save a human-reviewed version. Changed old questions require explicit ID mapping."""
    ordinal = question.get("number")
    kind = question.get("kind")
    if not isinstance(ordinal, int) or not 1 <= ordinal <= 100 or kind not in (
        "listening_news", "listening_dialogue", "listening_passage", "cloze", "matching",
        "careful", "writing", "translation"
    ) or not question.get("confirmed"):
        raise HTTPException(422, "题号、题型或人工确认缺失")
    answer = question.get("answer")
    if kind not in ("writing", "translation") and not answer:
        raise HTTPException(422, "客观题缺少答案")
    options = question.get("options") or []
    if options and answer not in options:
        raise HTTPException(422, "答案不在选项中")
    payload = json.dumps(options, ensure_ascii=False)
    stored_answer = json.dumps(answer, ensure_ascii=False)
    with connect() as db:
        if not db.execute("SELECT 1 FROM papers WHERE id=?", (paper_id,)).fetchone():
            raise HTTPException(404, "试卷不存在")
        existing = db.execute("SELECT id,question_kind FROM questions WHERE paper_id=? AND ordinal=?", (paper_id, ordinal)).fetchone()
        if existing:
            if existing["id"] != question.get("existing_question_id") or existing["question_kind"] != kind:
                raise HTTPException(409, "已有同题号题目，必须确认旧题 ID 映射且题型一致")
            question_id = existing["id"]
            previous = db.execute("SELECT version_no,prompt_text,options_json,correct_answer_json,rationale_text FROM question_versions WHERE question_id=? ORDER BY version_no DESC LIMIT 1", (question_id,)).fetchone()
            if (previous["prompt_text"], previous["options_json"], previous["correct_answer_json"], previous["rationale_text"]) == (
                question.get("prompt", ""), payload, stored_answer, question.get("rationale", "")):
                return {"id": question_id, "version": previous["version_no"], "unchanged": True}
            version = previous["version_no"] + 1
        else:
            question_id = str(uuid.uuid4())
            db.execute("INSERT INTO questions(id,paper_id,ordinal,question_kind,lifecycle,created_at) VALUES(?,?,?,?,?,?)",
                       (question_id, paper_id, ordinal, kind, "ready", now()))
            version = 1
        db.execute("INSERT INTO question_versions(id,question_id,version_no,prompt_text,options_json,correct_answer_json,rationale_text,verification_status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()), question_id, version, question.get("prompt", ""), payload,
                    stored_answer, question.get("rationale", ""), "verified", now()))
    return {"id": question_id, "version": version, "unchanged": False}
