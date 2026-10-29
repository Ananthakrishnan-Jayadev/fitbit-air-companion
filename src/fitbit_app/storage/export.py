"""Data export (ZIP of CSV files) and SQLite backups. Sync: run in worker threads."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import sqlite3
import zipfile
from pathlib import Path
from typing import IO, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitbit_app.storage.db import DB_FILE_MODE
from fitbit_app.storage.models import (
    ActivityMinute,
    AIInsight,
    Base,
    ChatMessage,
    DailyMetric,
    ExerciseSession,
    HrSample,
    HrvSample,
    JournalEntry,
    Score,
    SleepSession,
    SleepStage,
    Spo2Sample,
    UserProfile,
)
from fitbit_app.storage.types import utcnow

# Credentials (oauth_tokens), sync bookkeeping and raw API JSON are deliberately excluded.
SUMMARY_TABLES: dict[str, type[Base]] = {
    "daily_metrics": DailyMetric,
    "scores": Score,
    "sleep_sessions": SleepSession,
    "sleep_stages": SleepStage,
    "workouts": ExerciseSession,
    "journal": JournalEntry,
    "profile": UserProfile,
    "ai_insights": AIInsight,
    "coach_chat": ChatMessage,
}
INTRADAY_TABLES: dict[str, type[Base]] = {
    "heart_rate": HrSample,
    "hrv": HrvSample,
    "spo2": Spo2Sample,
    "activity_minutes": ActivityMinute,
}
BATCH_ROWS = 5000

README = """Fitbit Air Companion export ({created})

One CSV per table, UTF-8, header row first. Timestamps are UTC (ISO 8601); dates are local
days. JSON columns (score components, AI insight content, journal tags) are JSON strings.
{intraday}
"""


def write_export(session: Session, target: IO[bytes], *, include_intraday: bool) -> list[str]:
    """Write the ZIP to `target`; returns the CSV names written."""
    tables = dict(SUMMARY_TABLES)
    if include_intraday:
        tables.update(INTRADAY_TABLES)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, model in tables.items():
            with archive.open(f"{name}.csv", "w") as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                _write_csv(session, model, text)
                text.flush()
                text.detach()
        intraday_note = (
            "Intraday tables (heart_rate, hrv, spo2, activity_minutes) are included."
            if include_intraday
            else "Intraday tables were not included."
        )
        archive.writestr(
            "README.txt", README.format(created=utcnow().isoformat(), intraday=intraday_note)
        )
    return [f"{name}.csv" for name in tables]


def _write_csv(session: Session, model: type[Base], out: IO[str]) -> None:
    table = model.__table__
    writer = csv.writer(out)
    writer.writerow([c.name for c in table.columns])
    result = session.execute(select(table)).yield_per(BATCH_ROWS)
    for row in result:
        writer.writerow([_cell(value) for value in row])


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, dt.datetime | dt.date):
        return value.isoformat()
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return value


def backup_database(db_path: Path, out_dir: Path) -> Path:
    """Consistent online copy of the SQLite DB (safe while the server is running)."""
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = out_dir / f"fitbit-{utcnow():%Y%m%d-%H%M%S}.db"
    target.touch(mode=DB_FILE_MODE)
    os.chmod(target, DB_FILE_MODE)
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(target)
    try:
        with destination:
            source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target
