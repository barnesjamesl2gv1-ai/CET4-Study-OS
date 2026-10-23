"""Loopback-only API and bundled static frontend."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from backend.db import connect

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
