"""Environment checks for `fitbit doctor`."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from fitbit_app.ai.status import check_ollama
from fitbit_app.config import ENV_FILE, Settings
from fitbit_app.ingest.oauth import TokenStore
from fitbit_app.storage.db import create_db_engine, create_session_factory, ping
from fitbit_app.storage.migrate import current_revision, head_revision
from fitbit_app.storage.models import SyncState
from fitbit_app.storage.types import utcnow

STALE_AFTER = dt.timedelta(hours=24)


class Level(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckResult:
    name: str
    level: Level
    detail: str


async def run_checks(settings: Settings) -> list[CheckResult]:
    return [
        _check_env_file(),
        _check_google(settings),
        _check_secret_key(settings),
        await asyncio.to_thread(_check_database, settings),
        await asyncio.to_thread(_check_google_connection, settings),
        await asyncio.to_thread(_check_freshness, settings),
        _check_frontend(settings),
        await _check_ollama(settings),
    ]


def _check_env_file() -> CheckResult:
    if ENV_FILE.is_file():
        return CheckResult(".env", Level.OK, f"Found {ENV_FILE.resolve()}")
    return CheckResult(".env", Level.WARN, "Not found; using defaults. Copy .env.example to .env")


def _check_google(settings: Settings) -> CheckResult:
    if settings.google_configured:
        return CheckResult("Google OAuth", Level.OK, "Client ID and secret set")
    return CheckResult(
        "Google OAuth", Level.WARN, "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set (Phase 2)"
    )


def _check_secret_key(settings: Settings) -> CheckResult:
    if settings.fitbit_secret_key.get_secret_value():
        return CheckResult("Secret key", Level.OK, "FITBIT_SECRET_KEY set")
    return CheckResult(
        "Secret key", Level.WARN, "FITBIT_SECRET_KEY not set; needed to store Google tokens"
    )


def _check_database(settings: Settings) -> CheckResult:
    path = settings.db_path
    if not path.exists():
        return CheckResult("Database", Level.WARN, f"{path} not created yet; `serve` creates it")
    if not os.access(path, os.W_OK):
        return CheckResult("Database", Level.FAIL, f"{path} is not writable")

    engine = create_db_engine(path)
    try:
        ping(engine)
        current = current_revision(engine)
    except SQLAlchemyError as exc:
        return CheckResult("Database", Level.FAIL, f"Cannot open {path}: {type(exc).__name__}")
    finally:
        engine.dispose()

    head = head_revision()
    if current != head:
        return CheckResult(
            "Database", Level.WARN, f"Schema at {current}, latest is {head}. Run: fitbit db upgrade"
        )
    return CheckResult("Database", Level.OK, f"{path} (schema {current})")


def _check_google_connection(settings: Settings) -> CheckResult:
    name = "Google connection"
    if not settings.db_path.exists():
        return CheckResult(name, Level.WARN, "Not connected (no database yet)")
    engine = create_db_engine(settings.db_path)
    try:
        if current_revision(engine) != head_revision():
            return CheckResult(name, Level.WARN, "Unknown until the database is upgraded")
        stored = TokenStore(create_session_factory(engine), settings.fitbit_secret_key).load()
    except SQLAlchemyError as exc:
        return CheckResult(name, Level.WARN, f"Cannot read tokens: {type(exc).__name__}")
    finally:
        engine.dispose()
    if stored is None:
        return CheckResult(name, Level.WARN, "Not connected. Settings → Connect Google")
    if stored.needs_reauth:
        return CheckResult(name, Level.WARN, "Expired or revoked. Settings → Reconnect")
    return CheckResult(name, Level.OK, "Connected")


def _check_freshness(settings: Settings) -> CheckResult:
    name = "Data freshness"
    if not settings.db_path.exists():
        return CheckResult(name, Level.WARN, "No data yet")
    engine = create_db_engine(settings.db_path)
    try:
        if current_revision(engine) != head_revision():
            return CheckResult(name, Level.WARN, "Unknown until the database is upgraded")
        with create_session_factory(engine)() as session:
            last = session.scalar(select(func.max(SyncState.last_success_at)))
    except SQLAlchemyError as exc:
        return CheckResult(name, Level.WARN, f"Cannot read sync state: {type(exc).__name__}")
    finally:
        engine.dispose()
    if last is None:
        return CheckResult(name, Level.WARN, "Never synced")
    age = utcnow() - last
    hours = age.total_seconds() / 3600
    if age > STALE_AFTER:
        return CheckResult(name, Level.WARN, f"Last successful sync {hours:.0f} h ago")
    return CheckResult(name, Level.OK, f"Last successful sync {hours:.1f} h ago")


def _check_frontend(settings: Settings) -> CheckResult:
    if (settings.static_dir / "index.html").is_file():
        return CheckResult("Frontend build", Level.OK, f"Found in {settings.static_dir}")
    return CheckResult("Frontend build", Level.WARN, "Not built. Run: fitbit build-ui")


async def _check_ollama(settings: Settings) -> CheckResult:
    if not settings.ai_enabled:
        return CheckResult("Ollama", Level.WARN, "AI disabled (AI_ENABLED=false)")
    status = await check_ollama(settings.ollama_host, settings.ollama_model)
    if not status.reachable or not status.model_present:
        # AI is optional; the app runs without it.
        return CheckResult("Ollama", Level.WARN, status.detail or "Unavailable")
    return CheckResult("Ollama", Level.OK, f"{settings.ollama_host}, model {status.model}")
