"""Body composition summaries from sparse daily readings (weigh-ins aren't daily)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence


def latest(points: Sequence[tuple[dt.date, float]]) -> tuple[dt.date, float] | None:
    return max(points, key=lambda p: p[0]) if points else None


def change_since(points: Sequence[tuple[dt.date, float]], days: int) -> float | None:
    """Latest value minus the most recent reading at least `days` days before it.

    None when there is no reading that far back.
    """
    newest = latest(points)
    if newest is None:
        return None
    cutoff = newest[0] - dt.timedelta(days=days)
    earlier = [p for p in points if p[0] <= cutoff]
    if not earlier:
        return None
    return round(newest[1] - max(earlier, key=lambda p: p[0])[1], 2)


def split_mass(weight_kg: float, body_fat_pct: float) -> tuple[float, float]:
    """(fat mass, lean mass) in kg."""
    fat = weight_kg * body_fat_pct / 100
    return round(fat, 2), round(weight_kg - fat, 2)
