import csv
import datetime as dt
import io
import logging
import sqlite3
import stat
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from fitbit_app import cli as cli_module
from fitbit_app.config import Settings
from fitbit_app.ingest.oauth import TokenSet, TokenStore
from fitbit_app.logging_setup import LOG_FILE, configure_logging
from fitbit_app.main import create_app
from fitbit_app.storage.export import backup_database, write_export
from fixtures.scenario import build_scored_db

runner = CliRunner()


@pytest.fixture
def scored(session_factory: sessionmaker[Session], settings: Settings) -> sessionmaker[Session]:
    build_scored_db(session_factory)
    expires = dt.datetime(2030, 1, 1, tzinfo=dt.UTC)
    TokenStore(session_factory, settings.fitbit_secret_key).save(
        TokenSet("secret-access", "secret-refresh", expires, "", "Bearer")
    )
    return session_factory


def _zip(data: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(data))


def test_export_contents(scored: sessionmaker[Session]) -> None:
    buffer = io.BytesIO()
    with scored() as session:
        files = write_export(session, buffer, include_intraday=False)
    archive = _zip(buffer.getvalue())
    names = set(archive.namelist())
    assert set(files) <= names
    assert "README.txt" in names
    assert "heart_rate.csv" not in names
    rows = list(csv.DictReader(io.StringIO(archive.read("scores.csv").decode())))
    assert len(rows) == 21
    assert rows[0]["date"] == "2026-09-01"
    # Credentials never leave the database.
    everything = b"".join(archive.read(n) for n in names)
    assert b"secret-access" not in everything
    assert b"secret-refresh" not in everything


def test_export_with_intraday(scored: sessionmaker[Session]) -> None:
    buffer = io.BytesIO()
    with scored() as session:
        write_export(session, buffer, include_intraday=True)
    archive = _zip(buffer.getvalue())
    heart = list(csv.reader(io.StringIO(archive.read("heart_rate.csv").decode())))
    assert heart[0] == ["ts", "bpm", "motion_context"]
    assert len(heart) > 1000


def test_backup_is_a_private_consistent_copy(
    scored: sessionmaker[Session], settings: Settings, tmp_path: Path
) -> None:
    target = backup_database(settings.db_path, tmp_path / "backups")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with sqlite3.connect(target) as copy:
        assert copy.execute("SELECT count(*) FROM scores").fetchone()[0] == 21


@pytest.fixture
def scored_client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        build_scored_db(c.app.state.session_factory)
        yield c


def test_export_endpoint(scored_client: TestClient, settings: Settings) -> None:
    response = scored_client.get("/api/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert "scores.csv" in _zip(response.content).namelist()
    # The temporary file is cleaned up after sending.
    assert list(settings.data_dir.glob("export-*.zip")) == []


@pytest.fixture
def cli_settings(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr(cli_module, "get_settings", lambda: settings)
    return settings


def test_cli_export_and_backup(cli_settings: Settings, tmp_path: Path) -> None:
    out = tmp_path / "export.zip"
    result = runner.invoke(cli_module.app, ["export", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    assert "daily_metrics.csv" in zipfile.ZipFile(out).namelist()

    result = runner.invoke(cli_module.app, ["db", "backup", "--out", str(tmp_path / "b")])
    assert result.exit_code == 0, result.output
    assert len(list((tmp_path / "b").glob("fitbit-*.db"))) == 1


def test_cli_backup_without_database(cli_settings: Settings) -> None:
    result = runner.invoke(cli_module.app, ["db", "backup"])
    assert result.exit_code == 1


def test_log_file_is_written(tmp_path: Path) -> None:
    root = logging.getLogger()
    saved = list(root.handlers)
    try:
        configure_logging("INFO", tmp_path / "logs")
        logging.getLogger("fitbit_app.test").info("hello from the test")
        for handler in root.handlers:
            handler.flush()
        assert "hello from the test" in (tmp_path / "logs" / LOG_FILE).read_text()
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = saved
