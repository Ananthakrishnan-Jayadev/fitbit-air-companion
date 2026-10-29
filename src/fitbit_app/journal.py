"""Journal tags: normalization and the queries shared by the API, analytics and AI."""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitbit_app.analytics.correlations import TagEffect, tag_effects
from fitbit_app.storage.models import DailyMetric, JournalEntry, Score

# Suggested tags; users can add their own.
PRESET_TAGS = (
    "alcohol",
    "late_caffeine",
    "late_meal",
    "late_screen_time",
    "hard_workout",
    "nap",
    "stressful_day",
    "travel",
    "sick",
    "meditation",
    "sauna",
    "early_bedtime",
)
MAX_TAGS = 20
MAX_TAG_LENGTH = 30
MAX_NOTE_LENGTH = 2000

# Outcome -> (table, column). All are compared on the day after the tagged day.
OUTCOMES: dict[str, tuple[Any, str]] = {
    "recovery": (Score, "recovery"),
    "sleep_perf": (Score, "sleep_perf"),
    "hrv_rmssd_ms": (DailyMetric, "hrv_rmssd_ms"),
    "resting_hr": (DailyMetric, "resting_hr"),
    "sleep_min": (DailyMetric, "sleep_min"),
}

_NON_TAG_CHARS = re.compile(r"[^a-z0-9_]+")


def normalize_tags(tags: list[str]) -> list[str]:
    """Lowercase snake_case, de-duplicated, order kept: "Late Meal" -> "late_meal"."""
    seen: dict[str, None] = {}
    for raw in tags:
        tag = _NON_TAG_CHARS.sub("_", raw.strip().lower()).strip("_")[:MAX_TAG_LENGTH]
        if tag:
            seen.setdefault(tag, None)
    return list(seen)[:MAX_TAGS]


def tags_by_day(session: Session, start: dt.date, end: dt.date) -> dict[dt.date, list[str]]:
    rows = session.scalars(
        select(JournalEntry).where(JournalEntry.date >= start, JournalEntry.date <= end)
    ).all()
    return {row.date: list(row.tags or []) for row in rows}


def tag_counts(session: Session) -> Counter[str]:
    counts: Counter[str] = Counter()
    for tags in session.scalars(select(JournalEntry.tags)).all():
        counts.update(tags or [])
    return counts


def effects_for(
    session: Session, outcome: str, start: dt.date, end: dt.date
) -> tuple[list[TagEffect], int]:
    """(tag effects on `outcome`, number of logged days) for tags dated in [start, end]."""
    table, column = OUTCOMES[outcome]
    tags = tags_by_day(session, start, end)
    rows = session.execute(
        select(table.date, getattr(table, column)).where(
            table.date > start, table.date <= end + dt.timedelta(days=1)
        )
    ).all()
    values = {day: float(v) for day, v in rows if v is not None}
    return tag_effects(tags, values), len(tags)
