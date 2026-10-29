"""Compact, numbers-only summary of a day for the local LLM (project.md §8.2).

The LLM never sees raw series; it explains these values.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

# Relative change over the window that counts as a trend.
TREND_THRESHOLD = 0.03


def trend_direction(values: Sequence[float | None]) -> str | None:
    """'up' / 'down' / 'flat' from a least-squares slope over the window, or None."""
    points = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(points) < 4:
        return None
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    mean = float(ys.mean())
    if mean == 0:
        return None
    slope = float(np.polyfit(xs, ys, 1)[0])
    change = slope * (len(values) - 1) / abs(mean)
    if change >= TREND_THRESHOLD:
        return "up"
    if change <= -TREND_THRESHOLD:
        return "down"
    return "flat"


def feature_pack(
    *,
    day: dt.date,
    scores: Mapping[str, Any],
    metrics: Mapping[str, Any],
    z_scores: Mapping[str, float | None],
    trends: Mapping[str, str | None],
    flags: Sequence[str],
    sleep: Mapping[str, Any] | None = None,
    journal: Sequence[str] = (),
) -> dict[str, Any]:
    def rounded(mapping: Mapping[str, Any], digits: int = 1) -> dict[str, Any]:
        return {
            k: round(v, digits) if isinstance(v, float) else v
            for k, v in mapping.items()
            if v is not None
        }

    return {
        "date": day.isoformat(),
        "scores": rounded(scores),
        "metrics": rounded(metrics),
        "vs_baseline_z": rounded(z_scores, 2),
        "trend_7d": {k: v for k, v in trends.items() if v is not None},
        "sleep": rounded(sleep or {}),
        "flags": list(flags),
        "journal": list(journal),
    }
