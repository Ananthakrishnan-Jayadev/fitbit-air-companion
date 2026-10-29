import datetime as dt

import pandas as pd
import pytest

from fitbit_app.analytics.sleep import (
    SleepNight,
    asleep_minutes,
    minutes_since_evening,
    sleep_performance,
    stage_minutes,
)

T0 = dt.datetime(2026, 10, 1, 3, 0, tzinfo=dt.UTC)


def _stages(plan: list[tuple[str, float]]) -> pd.DataFrame:
    rows, t = [], T0
    for stage, minutes in plan:
        end = t + dt.timedelta(minutes=minutes)
        rows.append({"start_ts": t, "end_ts": end, "stage": stage})
        t = end
    return pd.DataFrame(rows, columns=["start_ts", "end_ts", "stage"])


def _night(plan: list[tuple[str, float]], efficiency: float | None = None) -> SleepNight:
    stages = _stages(plan)
    total = sum(m for _, m in plan)
    return SleepNight(T0, T0 + dt.timedelta(minutes=total), total, efficiency, stages)


GOOD_NIGHT = [("light", 200), ("deep", 100), ("rem", 120), ("awake", 10), ("light", 50)]


def test_stage_minutes_and_asleep() -> None:
    night = _night(GOOD_NIGHT)
    minutes = stage_minutes(night.stages)
    assert minutes == {"light": 250, "deep": 100, "rem": 120, "awake": 10}
    assert asleep_minutes(night) == 470


def test_asleep_fallbacks_without_stages() -> None:
    empty = pd.DataFrame(columns=["start_ts", "end_ts", "stage"])
    with_eff = SleepNight(T0, T0, 400, 90.0, empty)
    without = SleepNight(T0, T0, 400, None, empty)
    assert asleep_minutes(with_eff) == 360
    assert asleep_minutes(without) == 400


def test_good_night_scores_high() -> None:
    result = sleep_performance(_night(GOOD_NIGHT), need_min=480, bedtimes=[330, 335, 325, 330])
    assert result.score is not None
    assert result.score >= 90
    assert all(v is not None for v in result.components.values())


def test_short_night_scores_lower() -> None:
    short = [("light", 150), ("deep", 50), ("rem", 40)]
    good = sleep_performance(_night(GOOD_NIGHT), need_min=480).score
    bad = sleep_performance(_night(short), need_min=480).score
    assert good is not None and bad is not None
    assert bad < good


def test_irregular_bedtimes_lower_consistency() -> None:
    regular = sleep_performance(_night(GOOD_NIGHT), bedtimes=[330, 335, 325, 330])
    irregular = sleep_performance(_night(GOOD_NIGHT), bedtimes=[240, 420, 300, 480])
    irregular_score = irregular.components["consistency"]
    regular_score = regular.components["consistency"]
    assert irregular_score is not None and regular_score is not None
    assert irregular_score < regular_score


def test_consistency_needs_three_nights() -> None:
    result = sleep_performance(_night(GOOD_NIGHT), bedtimes=[330, 335])
    assert result.components["consistency"] is None
    assert result.score is not None  # other components renormalized


def test_minutes_since_evening_wraps_midnight() -> None:
    assert minutes_since_evening(dt.datetime(2026, 10, 1, 23, 30)) == 330
    assert minutes_since_evening(dt.datetime(2026, 10, 2, 0, 30)) == 390
    assert minutes_since_evening(dt.datetime(2026, 10, 2, 18, 0)) == 0


def test_component_bounds() -> None:
    result = sleep_performance(_night(GOOD_NIGHT, efficiency=99.0), need_min=240)
    for value in result.components.values():
        if value is not None:
            assert 0 <= value <= 100
    assert result.components["duration"] == pytest.approx(100)
