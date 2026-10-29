import datetime as dt
import math

import pandas as pd
import pytest

from fitbit_app.analytics.baselines import SD_FLOOR, Baseline, compute_baselines, zscore

DAY = dt.date(2026, 10, 1)


def _daily(values: dict[str, list[float | None]], end: dt.date = DAY) -> pd.DataFrame:
    n = len(next(iter(values.values())))
    index = pd.Index([end - dt.timedelta(days=n - i) for i in range(n)], name="date")
    return pd.DataFrame(values, index=index)


def test_uses_only_days_before_as_of() -> None:
    daily = _daily({"resting_hr": [60.0] * 10})
    daily.loc[DAY, "resting_hr"] = 90.0  # today must not count
    baseline = compute_baselines(daily, DAY)["resting_hr"]
    assert baseline.mean == 60.0
    assert baseline.n == 10


def test_window_limits_history() -> None:
    daily = _daily({"resting_hr": [80.0] * 20 + [60.0] * 30})
    assert compute_baselines(daily, DAY, window_days=30)["resting_hr"].mean == 60.0


def test_requires_minimum_days() -> None:
    daily = _daily({"resting_hr": [60.0] * 6})
    assert "resting_hr" not in compute_baselines(daily, DAY, min_days=7)


def test_missing_values_are_ignored() -> None:
    daily = _daily({"resting_hr": [60.0, None] * 8})
    assert compute_baselines(daily, DAY)["resting_hr"].n == 8


def test_sd_floor() -> None:
    daily = _daily({"resting_hr": [60.0] * 10})
    assert compute_baselines(daily, DAY)["resting_hr"].sd == SD_FLOOR["resting_hr"]


def test_hrv_uses_log_scale() -> None:
    daily = _daily({"hrv_rmssd_ms": [40.0, 60.0] * 5})
    baseline = compute_baselines(daily, DAY)["hrv_rmssd_ms"]
    assert baseline.mean == pytest.approx((math.log(40) + math.log(60)) / 2)
    assert baseline.typical == pytest.approx(math.sqrt(40 * 60))
    low, high = baseline.band()
    assert low < baseline.typical < high


def test_zscore() -> None:
    baseline = Baseline("resting_hr", mean=60.0, sd=2.0, n=30)
    assert zscore(64.0, baseline) == 2.0
    assert zscore(None, baseline) is None
    assert zscore(float("nan"), baseline) is None
    assert zscore(64.0, None) is None


def test_zscore_log_metric() -> None:
    baseline = Baseline("hrv_rmssd_ms", mean=math.log(50), sd=0.1, n=30)
    assert zscore(50.0, baseline) == pytest.approx(0.0)
    assert zscore(50.0 * math.exp(0.2), baseline) == pytest.approx(2.0)
    assert zscore(0.0, baseline) is None
