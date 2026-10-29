"""Daily activity values the API does not provide directly."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Iterable


def sedentary_minutes_by_day(
    periods: Iterable[tuple[dt.datetime, dt.datetime, dt.timedelta]],
) -> dict[dt.date, float]:
    """Sum sedentary periods (start UTC, end UTC, UTC offset) per local day, split at midnight."""
    totals: dict[dt.date, float] = defaultdict(float)
    for start, end, offset in periods:
        local_start, local_end = start + offset, end + offset
        cursor = local_start
        while cursor < local_end:
            next_midnight = dt.datetime.combine(
                cursor.date() + dt.timedelta(days=1), dt.time(), tzinfo=cursor.tzinfo
            )
            segment_end = min(local_end, next_midnight)
            totals[cursor.date()] += (segment_end - cursor).total_seconds() / 60
            cursor = segment_end
    return {day: round(minutes, 1) for day, minutes in totals.items()}
