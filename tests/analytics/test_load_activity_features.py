import datetime as dt

import numpy as np
import pytest

from fitbit_app.analytics.activity import sedentary_minutes_by_day
from fitbit_app.analytics.downsample import lttb_indices
from fitbit_app.analytics.features import feature_pack, trend_direction
from fitbit_app.analytics.load import acute_chronic_ratio, load_flag

DAY = dt.date(2026, 10, 28)


def _strains(values: list[float | None]) -> dict[dt.date, float | None]:
    """values[0] is DAY, values[1] the day before, ..."""
    return {DAY - dt.timedelta(days=i): v for i, v in enumerate(values)}


# --- load --------------------------------------------------------------------------------


def test_steady_load_ratio_is_one() -> None:
    assert acute_chronic_ratio(_strains([10.0] * 28), DAY) == 1.0


def test_recent_spike() -> None:
    ratio = acute_chronic_ratio(_strains([18.0] * 7 + [8.0] * 21), DAY)
    assert ratio is not None and ratio > 1.5
    assert load_flag(ratio) == "load_spike"


def test_needs_enough_history() -> None:
    assert acute_chronic_ratio(_strains([10.0] * 14), DAY) is None
    assert acute_chronic_ratio(_strains([None] * 28), DAY) is None


def test_load_flags() -> None:
    assert load_flag(0.7) == "load_low"
    assert load_flag(1.0) is None
    assert load_flag(None) is None


# --- sedentary ---------------------------------------------------------------------------


def test_sedentary_split_at_local_midnight() -> None:
    edt = dt.timedelta(hours=-4)
    # 23:00 -> 01:00 local (03:00 -> 05:00 UTC)
    start = dt.datetime(2026, 10, 2, 3, 0, tzinfo=dt.UTC)
    end = dt.datetime(2026, 10, 2, 5, 0, tzinfo=dt.UTC)
    totals = sedentary_minutes_by_day([(start, end, edt)])
    assert totals == {dt.date(2026, 10, 1): 60.0, dt.date(2026, 10, 2): 60.0}


# --- downsampling ------------------------------------------------------------------------


def test_lttb_keeps_endpoints_and_size() -> None:
    x = np.arange(1000)
    y = np.sin(x / 50)
    idx = lttb_indices(x, y, 100)
    assert len(idx) == 100
    assert idx[0] == 0 and idx[-1] == 999
    assert (np.diff(idx) > 0).all()


def test_lttb_keeps_a_spike() -> None:
    x = np.arange(1000)
    y = np.zeros(1000)
    y[537] = 100
    assert 537 in lttb_indices(x, y, 50)


def test_lttb_small_input_unchanged() -> None:
    assert list(lttb_indices(np.arange(5), np.arange(5), 10)) == [0, 1, 2, 3, 4]


# --- features ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([50, 51, 52, 53, 54, 55, 56], "up"),
        ([56, 55, 54, 53, 52, 51, 50], "down"),
        ([50, 50.2, 49.9, 50.1, 50, 49.8, 50], "flat"),
        ([50, None, None, 52], None),
    ],
)
def test_trend_direction(values: list[float | None], expected: str | None) -> None:
    assert trend_direction(values) == expected


def test_feature_pack_rounds_and_drops_missing() -> None:
    pack = feature_pack(
        day=DAY,
        scores={"recovery": 62.345, "strain": None},
        metrics={"resting_hr": 57.0},
        z_scores={"hrv_rmssd_ms": -1.23456},
        trends={"hrv": "down", "rhr": None},
        flags=["hrv_suppressed"],
    )
    assert pack == {
        "date": "2026-10-28",
        "scores": {"recovery": 62.3},
        "metrics": {"resting_hr": 57.0},
        "vs_baseline_z": {"hrv_rmssd_ms": -1.23},
        "trend_7d": {"hrv": "down"},
        "sleep": {},
        "flags": ["hrv_suppressed"],
        "journal": [],
    }
