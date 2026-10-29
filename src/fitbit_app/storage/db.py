"""SQLite engine and sessions.

The DB layer is synchronous SQLAlchemy. Callers on the event loop must use it from FastAPI
`def` handlers (run in the threadpool) or via `asyncio.to_thread`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

DB_FILE_MODE = 0o600


def create_db_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_private_file(db_path)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def ping(engine: Engine) -> None:
    """Raises a SQLAlchemyError if the database is unusable."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _ensure_private_file(path: Path) -> None:
    # Create before SQLite does, so the file never exists with looser permissions.
    # SQLite gives its -wal/-shm files the same mode as the main file.
    if not path.exists():
        path.touch(mode=DB_FILE_MODE)
    os.chmod(path, DB_FILE_MODE)


def _set_sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
