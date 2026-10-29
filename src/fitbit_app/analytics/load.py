"""Training load: acute (7-day) vs chronic (28-day) average strain."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

ACUTE_DAYS = 7
CHRONIC_DAYS = 28
MIN_CHRONIC_DAYS = 21
SPIKE_RATIO = 1.5
DETRAINING_RATIO = 0.8


def acute_chronic_ratio(
    strain_by_day: Mapping[dt.date, float | None], as_of: dt.date
) -> float | None:
    """Mean strain of the last 7 days / last 28 days (both including `as_of`)."""

    def window(days: int) -> list[float]:
        return [
            v
            for offset in range(days)
            if (v := strain_by_day.get(as_of - dt.timedelta(days=offset))) is not None
        ]

    chronic = window(CHRONIC_DAYS)
    acute = window(ACUTE_DAYS)
    if len(chronic) < MIN_CHRONIC_DAYS or not acute:
        return None
    chronic_mean = sum(chronic) / len(chronic)
    if chronic_mean <= 0:
        return None
    return round((sum(acute) / len(acute)) / chronic_mean, 2)


def load_flag(ratio: float | None) -> str | None:
    if ratio is None:
        return None
    if ratio >= SPIKE_RATIO:
        return "load_spike"
    if ratio <= DETRAINING_RATIO:
        return "load_low"
    return None
