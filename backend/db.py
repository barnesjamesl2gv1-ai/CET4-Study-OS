"""SQLite access. Persistent data always lives outside the installation directory."""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path

DATABASE_LOCK = threading.RLock()


def data_dir() -> Path:
    root = Path(os.environ.get("CET4_DATA_DIR") or
                Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CET4StudyOS")
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return data_dir() / "study.sqlite3"


def initialize(path: Path | None = None) -> Path:
    target = path or database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(__file__).resolve().parents[1] / "docs" / "spec" / "03_数据库草案.sql"
    with closing(sqlite3.connect(target)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(schema.read_text(encoding="utf-8"))
        db.execute("INSERT OR IGNORE INTO schema_meta(key,value) VALUES('schema_version','1')")
        db.commit()
    return target


@contextmanager
def connect(path: Path | None = None):
    with DATABASE_LOCK:
        target = initialize(path)
        db = sqlite3.connect(target)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
