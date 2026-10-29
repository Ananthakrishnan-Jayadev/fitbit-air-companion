"""Daytime stress: heart rate elevated above resting while you are sitting still.

A minute qualifies when Google's activity level is SEDENTARY (or, without a level, under 10
steps), you are not asleep, and there was no activity in the previous 10 minutes (so
recovering from a walk doesn't read as stress). Stress = (HR - resting) / 30 bpm, as 0-100.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

STRESS_RANGE_BPM = 30.0
SETTLE_MINUTES = 10
CALM_STEPS = 10
HIGH_STRESS = 60.0
MIN_VALID_MINUTES = 30
SEDENTARY = "SEDENTARY"


@dataclass(frozen=True)
class DailyStress:
    average: float | None
    high_minutes: int
    valid_minutes: int


def stress_timeline(
    hr: pd.DataFrame,
    activity: pd.DataFrame,
    resting_hr: float,
    asleep: Sequence[tuple[dt.datetime, dt.datetime]] = (),
) -> pd.DataFrame:
    """Per-minute frame indexed by minute (UTC) with columns `hr` and `stress` (NaN if n/a).

    `hr`: columns ts, bpm. `activity`: columns ts (minute), activity_level, steps.
    """
    if hr.empty:
        return pd.DataFrame(columns=["hr", "stress"], dtype=float)
    per_minute = hr.set_index("ts")["bpm"].astype(float).resample("1min").mean()
    frame = pd.DataFrame({"hr": per_minute})

    activity = activity.set_index("ts") if not activity.empty else activity
    level = activity["activity_level"].reindex(frame.index) if not activity.empty else None
    steps = activity["steps"].reindex(frame.index) if not activity.empty else None

    if level is not None and steps is not None:
        calm = np.where(level.notna(), level == SEDENTARY, steps.fillna(0) < CALM_STEPS)
    else:
        calm = np.zeros(len(frame), dtype=bool)
    active = pd.Series(~calm, index=frame.index).astype(float)
    # Active in this minute or any of the previous SETTLE_MINUTES.
    recently_active = active.rolling(SETTLE_MINUTES + 1, min_periods=1).max().astype(bool)

    sleeping = np.zeros(len(frame), dtype=bool)
    for start, end in asleep:
        sleeping |= (frame.index >= start) & (frame.index < end)

    qualifies = calm & ~recently_active.to_numpy() & ~sleeping & frame["hr"].notna().to_numpy()
    stress = ((frame["hr"] - resting_hr) / STRESS_RANGE_BPM * 100).clip(0, 100)
    frame["stress"] = stress.where(qualifies)
    return frame


def daily_stress(timeline: pd.DataFrame) -> DailyStress:
    values = timeline["stress"].dropna() if "stress" in timeline else pd.Series(dtype=float)
    high = int((values >= HIGH_STRESS).sum())
    if len(values) < MIN_VALID_MINUTES:
        return DailyStress(None, high, len(values))
    return DailyStress(round(float(values.mean()), 1), high, len(values))
