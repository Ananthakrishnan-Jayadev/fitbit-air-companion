import datetime as dt

import pandas as pd
import pytest

from fitbit_app.analytics.stress import daily_stress, stress_timeline

T0 = dt.datetime(2026, 10, 1, 14, 0, tzinfo=dt.UTC)


def _hr(minutes: int, bpm: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": [T0 + dt.timedelta(seconds=15 * i) for i in range(minutes * 4)],
            "bpm": [bpm] * (minutes * 4),
        }
    )


def _activity(levels: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": [T0 + dt.timedelta(minutes=i) for i in range(len(levels))],
            "activity_level": levels,
            "steps": [0] * len(levels),
        }
    )


def test_calm_elevated_heart_rate_is_stress() -> None:
    timeline = stress_timeline(_hr(60, 75), _activity(["SEDENTARY"] * 60), resting_hr=60)
    # 15 bpm over resting out of a 30 bpm range -> 50
    assert timeline["stress"].dropna().iloc[0] == pytest.approx(50)
    assert len(timeline["stress"].dropna()) == 60


def test_activity_and_settle_window_are_excluded() -> None:
    levels = ["SEDENTARY"] * 20 + ["VERY_ACTIVE"] * 5 + ["SEDENTARY"] * 35
    timeline = stress_timeline(_hr(60, 80), _activity(levels), resting_hr=60)
    stress = timeline["stress"]
    assert stress.iloc[20:25].isna().all()  # active
    assert stress.iloc[25:35].isna().all()  # settling
    assert stress.iloc[:20].notna().all()
    assert stress.iloc[35:].notna().all()


def test_sleep_is_excluded() -> None:
    asleep = [(T0, T0 + dt.timedelta(minutes=30))]
    timeline = stress_timeline(_hr(60, 70), _activity(["SEDENTARY"] * 60), 60, asleep)
    assert timeline["stress"].iloc[:30].isna().all()
    assert timeline["stress"].iloc[30:].notna().all()


def test_steps_used_when_level_missing() -> None:
    activity = pd.DataFrame(
        {
            "ts": [T0 + dt.timedelta(minutes=i) for i in range(60)],
            "activity_level": [None] * 60,
            "steps": [0] * 30 + [120] * 30,
        }
    )
    timeline = stress_timeline(_hr(60, 70), activity, resting_hr=60)
    assert timeline["stress"].iloc[:30].notna().all()
    assert timeline["stress"].iloc[30:].isna().all()


def test_no_activity_data_means_no_stress() -> None:
    empty = pd.DataFrame(columns=["ts", "activity_level", "steps"])
    timeline = stress_timeline(_hr(30, 90), empty, resting_hr=60)
    assert timeline["stress"].isna().all()


def test_daily_stress_needs_enough_minutes() -> None:
    enough = stress_timeline(_hr(60, 78), _activity(["SEDENTARY"] * 60), resting_hr=60)
    result = daily_stress(enough)
    assert result.average == pytest.approx(60)
    assert result.high_minutes == 60
    assert result.valid_minutes == 60

    few = stress_timeline(_hr(10, 78), _activity(["SEDENTARY"] * 10), resting_hr=60)
    assert daily_stress(few).average is None


def test_empty_heart_rate() -> None:
    empty = pd.DataFrame(columns=["ts", "bpm"])
    assert stress_timeline(empty, _activity([]), resting_hr=60).empty
