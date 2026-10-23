"""Verified local backups using SQLite's online backup API."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from backend.db import DATABASE_LOCK, connect, data_dir, database_path, initialize
from backend.imports import now

MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def backup(kind: str = "manual") -> dict:
    if kind not in ("manual", "daily", "pre_upgrade", "pre_restore"):
        raise ValueError("备份类别无效")
    root = data_dir()
    folder = root / "backups"
    folder.mkdir(exist_ok=True)
    backup_id = str(uuid.uuid4())
    target = folder / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{backup_id}.zip"
    with DATABASE_LOCK, tempfile.TemporaryDirectory(dir=root) as scratch:
        snapshot = Path(scratch) / "database.sqlite3"
        with closing(sqlite3.connect(initialize())) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        with closing(sqlite3.connect(snapshot)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("数据库完整性检查失败")
            references = [(row[0], row[1]) for row in db.execute("SELECT DISTINCT relative_path,sha256 FROM source_assets")]
        files = {"database.sqlite3": snapshot.read_bytes()}
        for relative, expected_hash in references:
            path = (root / relative).resolve()
            if not path.is_relative_to(root / "assets") or not path.is_file():
                raise ValueError(f"源文件缺失或路径无效：{relative}")
            content = path.read_bytes()
            if digest(content) != expected_hash:
                raise ValueError(f"源文件哈希不匹配：{relative}")
            files[relative.replace("\\", "/")] = content
        manifest = {name: {"sha256": digest(data), "size": len(data)} for name, data in files.items()}
        temporary = Path(scratch) / "backup.zip"
        manifest_bytes = json.dumps({"version": 1, "files": manifest}, sort_keys=True).encode()
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
            archive.writestr("manifest.json", manifest_bytes)
        verify(temporary)
        os.replace(temporary, target)
        with connect() as db:
            db.execute("INSERT INTO backup_records(id,created_at,backup_kind,relative_path,manifest_sha256,verified) VALUES(?,?,?,?,?,1)",
                       (backup_id, now(), kind, str(target.relative_to(root)), digest(manifest_bytes)))
    return {"id": backup_id, "kind": kind, "path": str(target), "files": len(files)}


def verify(path: Path) -> dict:
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("备份文件过大")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names or "database.sqlite3" not in names:
            raise ValueError("备份缺少清单或数据库")
        if len(archive.namelist()) != len(names) or len(names) > 5000 or archive.getinfo("manifest.json").file_size > 1024 * 1024:
            raise ValueError("备份文件清单无效")
        manifest = json.loads(archive.read("manifest.json"))
        files = manifest.get("files", {})
        if not isinstance(files, dict) or manifest.get("version") != 1 or names != set(files) | {"manifest.json"}:
            raise ValueError("备份文件清单不匹配")
        if sum(info.file_size for info in archive.infolist()) > MAX_ARCHIVE_BYTES:
            raise ValueError("备份解压后过大")
        for name, meta in files.items():
            if not isinstance(name, str) or not isinstance(meta, dict) or not isinstance(meta.get("size"), int) or not isinstance(meta.get("sha256"), str):
                raise ValueError("备份清单字段无效")
            relative = Path(name)
            if name != "database.sqlite3" and (not name.startswith("assets/") or ".." in relative.parts or ":" in name or "\\" in name):
                raise ValueError("备份包含非法路径")
            if meta["size"] > MAX_ARCHIVE_BYTES:
                raise ValueError("备份单个文件过大")
            if archive.getinfo(name).file_size != meta["size"]:
                raise ValueError("备份文件大小与清单不符")
            content = archive.read(name)
            if len(content) != meta["size"] or digest(content) != meta["sha256"]:
                raise ValueError(f"备份文件校验失败：{name}")
        with tempfile.TemporaryDirectory() as scratch:
            db_path = Path(scratch) / "database.sqlite3"
            db_path.write_bytes(archive.read("database.sqlite3"))
            try:
                with closing(sqlite3.connect(db_path)) as db:
                    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("备份数据库损坏")
                    version = db.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
                    if not version or version[0] != "1":
                        raise ValueError("备份数据库版本不兼容")
                    for relative, expected_hash in db.execute("SELECT relative_path,sha256 FROM source_assets"):
                        name = relative.replace("\\", "/")
                        if name not in files or files[name]["sha256"] != expected_hash:
                            raise ValueError(f"备份缺少关联文件或哈希不匹配：{name}")
            except sqlite3.DatabaseError as error:
                raise ValueError("备份数据库损坏") from error
    return manifest


def restore(path: Path) -> dict:
    manifest = verify(path)
    root = data_dir()
    with DATABASE_LOCK:
        previous = backup("pre_restore")
        with tempfile.TemporaryDirectory(dir=root) as scratch:
            stage = Path(scratch)
            with zipfile.ZipFile(path) as archive:
                for name in manifest["files"]:
                    destination = stage / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(name))
            for name in manifest["files"]:
                if not name.startswith("assets/"):
                    continue
                destination = root / name
                if destination.exists() and digest(destination.read_bytes()) != manifest["files"][name]["sha256"]:
                    raise ValueError(f"现有文件与备份冲突，已保留原数据：{name}")
            database = database_path()
            with closing(sqlite3.connect(database)) as db:
                db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            rollback = stage / "rollback.sqlite3"
            os.replace(database, rollback)
            try:
                for name in manifest["files"]:
                    if name.startswith("assets/"):
                        destination = root / name
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if not destination.exists():
                            shutil.copy2(stage / name, destination)
                os.replace(stage / "database.sqlite3", database)
                with closing(sqlite3.connect(database)) as db:
                    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("恢复后的数据库校验失败")
            except Exception:
                os.replace(rollback, database)
                raise
    return {"restored": True, "pre_restore_backup": previous["path"]}


def daily_if_needed() -> dict | None:
    today = datetime.now().astimezone().date()
    with connect() as db:
        records = [row[0] for row in db.execute("SELECT created_at FROM backup_records WHERE backup_kind='daily'")]
        exists = any(datetime.fromisoformat(value).astimezone().date() == today for value in records)
    return None if exists else backup("daily")
