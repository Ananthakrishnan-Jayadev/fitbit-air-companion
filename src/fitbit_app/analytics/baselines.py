"""Personal baselines: rolling mean/SD of daily metrics over the previous N days."""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

BASELINE_METRICS = (
    "resting_hr",
    "hrv_rmssd_ms",
    "spo2_avg",
    "respiratory_rate",
    "skin_temp_delta_c",
    "sleep_min",
)
# HRV is roughly log-normal, so its baseline and z-scores use ln(value).
LOG_METRICS = frozenset({"hrv_rmssd_ms"})
# Lower bounds on SD so a very stable stretch doesn't turn tiny changes into huge z-scores.
SD_FLOOR = {
    "resting_hr": 1.0,
    "hrv_rmssd_ms": 0.05,
    "spo2_avg": 0.3,
    "respiratory_rate": 0.3,
    "skin_temp_delta_c": 0.1,
    "sleep_min": 20.0,
}
WINDOW_DAYS = 30
MIN_DAYS = 7


@dataclass(frozen=True)
class Baseline:
    metric: str
    mean: float  # ln scale for LOG_METRICS
    sd: float
    n: int

    @property
    def typical(self) -> float:
        """Mean in natural units (geometric mean for log metrics)."""
        return math.exp(self.mean) if self.metric in LOG_METRICS else self.mean

    def band(self) -> tuple[float, float]:
        """Mean ± 1 SD in natural units."""
        low, high = self.mean - self.sd, self.mean + self.sd
        if self.metric in LOG_METRICS:
            return math.exp(low), math.exp(high)
        return low, high


def compute_baselines(
    daily: pd.DataFrame,
    as_of: dt.date,
    *,
    window_days: int = WINDOW_DAYS,
    min_days: int = MIN_DAYS,
) -> dict[str, Baseline]:
    """Baselines from days in [as_of - window_days, as_of); `as_of` itself is excluded.

    `daily` is indexed by `datetime.date` with one column per metric.
    """
    start = as_of - dt.timedelta(days=window_days)
    in_window = [start <= day < as_of for day in daily.index]
    window = daily.loc[in_window]
    result: dict[str, Baseline] = {}
    for metric in BASELINE_METRICS:
        if metric not in window.columns:
            continue
        values = pd.to_numeric(window[metric], errors="coerce").dropna().astype(float)
        if metric in LOG_METRICS:
            values = np.log(values[values > 0])
        if len(values) < min_days:
            continue
        sd = max(float(values.std(ddof=1)), SD_FLOOR[metric])
        result[metric] = Baseline(metric, float(values.mean()), sd, len(values))
    return result


def zscore(value: float | None, baseline: Baseline | None) -> float | None:
    if value is None or baseline is None or pd.isna(value):
        return None
    x = float(value)
    if baseline.metric in LOG_METRICS:
        if x <= 0:
            return None
        x = math.log(x)
    return (x - baseline.mean) / baseline.sd
