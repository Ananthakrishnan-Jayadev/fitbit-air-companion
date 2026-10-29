import stat
from pathlib import Path

from sqlalchemy import text

from fitbit_app.storage.db import DB_FILE_MODE, create_db_engine, ping


def test_creates_parent_dir_and_private_file(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "fitbit.db"
    engine = create_db_engine(db_path)
    try:
        assert db_path.is_file()
        assert stat.S_IMODE(db_path.stat().st_mode) == DB_FILE_MODE
    finally:
        engine.dispose()


def test_tightens_permissions_of_existing_file(tmp_path: Path) -> None:
    db_path = tmp_path / "fitbit.db"
    db_path.touch(mode=0o644)
    db_path.chmod(0o644)
    create_db_engine(db_path).dispose()
    assert stat.S_IMODE(db_path.stat().st_mode) == DB_FILE_MODE


def test_pragmas_applied(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "fitbit.db")
    try:
        with engine.connect() as conn:
            assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000
    finally:
        engine.dispose()


def test_ping(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "fitbit.db")
    try:
        ping(engine)
    finally:
        engine.dispose()
