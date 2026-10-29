"""Strain (0-21) from intraday heart rate, using Banister's TRIMP on heart-rate reserve.

TRIMP = sum(minutes * HRr * 0.64 * e^(1.92 * HRr)) where HRr = (HR - rest) / (max - rest).
Only time at HRr >= 0.3 counts, so everyday low-intensity heart rate doesn't add up to a
"hard" day. Strain is log-scaled: 21 * ln(1 + TRIMP) / ln(1 + 400), capped at 21.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

HRR_THRESHOLD = 0.3
TRIMP_AT_MAX_STRAIN = 400.0
MAX_STRAIN = 21.0
# A gap longer than this between samples is missing data, not a long sample.
MAX_SAMPLE_GAP_S = 60.0
FALLBACK_MAX_HR = 190.0


@dataclass(frozen=True)
class StrainResult:
    strain: float
    trimp: float
    minutes_counted: float


def estimate_max_hr(
    age: int | None, profile_max_hr: int | None, observed_high: float | None
) -> tuple[float, str]:
    """(max HR, method). Prefers the profile, then age (Tanaka), then observed data."""
    if profile_max_hr:
        return float(profile_max_hr), "profile"
    if age:
        return 208 - 0.7 * age, "age"
    if observed_high:
        # Observed peaks underestimate true max for people who rarely go all out.
        return float(min(210.0, max(170.0, observed_high))), "observed"
    return FALLBACK_MAX_HR, "default"


def trimp(hr: pd.DataFrame, resting_hr: float, max_hr: float) -> tuple[float, float]:
    """(TRIMP, minutes counted) for samples with columns ts (UTC), bpm."""
    if max_hr <= resting_hr:
        raise ValueError("max_hr must exceed resting_hr")
    if len(hr) < 2:
        return 0.0, 0.0
    ordered = hr.sort_values("ts")
    seconds = ordered["ts"].diff().shift(-1).dt.total_seconds()
    seconds = seconds.fillna(seconds.median()).clip(upper=MAX_SAMPLE_GAP_S).to_numpy()
    hrr = ((ordered["bpm"].to_numpy(dtype=float) - resting_hr) / (max_hr - resting_hr)).clip(0, 1)
    counted = hrr >= HRR_THRESHOLD
    minutes = seconds[counted] / 60
    load = minutes * hrr[counted] * 0.64 * np.exp(1.92 * hrr[counted])
    return float(load.sum()), float(minutes.sum())


def strain_from_trimp(value: float) -> float:
    scaled = MAX_STRAIN * math.log1p(max(0.0, value)) / math.log1p(TRIMP_AT_MAX_STRAIN)
    return round(min(MAX_STRAIN, scaled), 1)


def day_strain(hr: pd.DataFrame, resting_hr: float, max_hr: float) -> StrainResult:
    load, minutes = trimp(hr, resting_hr, max_hr)
    return StrainResult(strain_from_trimp(load), round(load, 1), round(minutes, 1))


def strain_target(recovery: float | None) -> tuple[float, float] | None:
    """Suggested strain range for the day, by recovery."""
    if recovery is None:
        return None
    if recovery >= 67:
        return 14.0, 18.0
    if recovery >= 34:
        return 10.0, 14.0
    return 6.0, 10.0
