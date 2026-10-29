"""Parsing and formatting of the Google Health API time representations.

- Physical times: RFC-3339 strings, e.g. "2026-04-20T22:30:00Z" (may carry nanoseconds)
- UTC offsets: Duration strings in whole seconds, e.g. "-14400s"
- Dates: google.type.Date objects {"year": 2026, "month": 4, "day": 20}
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

_EXCESS_FRACTION = re.compile(r"(\.\d{6})\d+")


def parse_ts(value: str) -> dt.datetime:
    # datetime.fromisoformat accepts at most microseconds.
    parsed = dt.datetime.fromisoformat(_EXCESS_FRACTION.sub(r"\1", value))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp without offset: {value!r}")
    return parsed.astimezone(dt.UTC)


def parse_offset(value: str | None) -> dt.timedelta:
    if not value:
        return dt.timedelta(0)
    if not value.endswith("s"):
        raise ValueError(f"Unexpected offset format: {value!r}")
    return dt.timedelta(seconds=float(value[:-1]))


def parse_duration_minutes(value: str | None) -> float | None:
    """Duration string such as "3600s" or "3.5s" -> minutes."""
    if not value:
        return None
    return parse_offset(value).total_seconds() / 60


def parse_date(value: dict[str, Any]) -> dt.date:
    return dt.date(int(value["year"]), int(value["month"]), int(value["day"]))


def to_rfc3339(ts: dt.datetime) -> str:
    return ts.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_civil_date(day: dt.date) -> dict[str, int]:
    return {"year": day.year, "month": day.month, "day": day.day}


def start_of_day_utc(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(), tzinfo=dt.UTC)


def floor_minute(ts: dt.datetime) -> dt.datetime:
    return ts.replace(second=0, microsecond=0)
