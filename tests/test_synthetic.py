import datetime as dt

import pandas as pd
import pytest

from fixtures.synthetic import STAGES, generate

START = dt.date(2026, 9, 1)


def test_same_seed_is_deterministic() -> None:
    a = generate(START, days=3, seed=7)
    b = generate(START, days=3, seed=7)
    pd.testing.assert_frame_equal(a.hr, b.hr)
    pd.testing.assert_frame_equal(a.sleep_stages, b.sleep_stages)
    pd.testing.assert_frame_equal(a.daily, b.daily)


def test_different_seed_differs() -> None:
    assert not generate(START, days=3, seed=1).hr.equals(generate(START, days=3, seed=2).hr)


def test_rejects_zero_days() -> None:
    with pytest.raises(ValueError):
        generate(START, days=0)


def test_one_sleep_session_per_day_assigned_to_wake_date() -> None:
    data = generate(START, days=5)
    sessions = data.sleep_sessions
    assert list(sessions["local_date"]) == [START + dt.timedelta(days=i) for i in range(5)]
    assert (sessions["end_ts"] > sessions["start_ts"]).all()
    assert sessions["duration_min"].between(240, 600).all()
    assert (sessions["end_ts"].dt.date == sessions["local_date"]).all()


def test_stages_are_contiguous_and_cover_each_session() -> None:
    data = generate(START, days=4)
    for session in data.sleep_sessions.itertuples():
        stages = data.sleep_stages[data.sleep_stages["session_id"] == session.session_id]
        assert stages["start_ts"].iloc[0] == session.start_ts
        assert stages["end_ts"].iloc[-1] == session.end_ts
        starts = stages["start_ts"].iloc[1:].to_numpy()
        assert (starts == stages["end_ts"].iloc[:-1].to_numpy()).all()
        assert set(stages["stage"]) <= set(STAGES)


def test_timestamps_are_utc() -> None:
    data = generate(START, days=2, tz="America/Toronto")
    for frame in (data.hr, data.hrv, data.spo2, data.activity):
        assert str(frame["ts"].dt.tz) == "UTC"


def test_heart_rate_is_plausible_and_lower_asleep() -> None:
    data = generate(START, days=5)
    assert data.hr["bpm"].between(40, 200).all()
    first = data.sleep_sessions.iloc[0]
    asleep = data.hr[(data.hr["ts"] >= first.start_ts) & (data.hr["ts"] < first.end_ts)]
    awake = data.hr[data.hr["ts"] >= first.end_ts]
    assert asleep["bpm"].median() < awake["bpm"].median()


def test_hr_interval_controls_resolution() -> None:
    coarse = generate(START, days=1, hr_interval_s=60)
    fine = generate(START, days=1, hr_interval_s=5)
    assert len(fine.hr) == pytest.approx(len(coarse.hr) * 12, rel=0.01)


def test_no_steps_while_asleep() -> None:
    data = generate(START, days=3)
    for session in data.sleep_sessions.itertuples():
        during = data.activity[
            (data.activity["ts"] >= session.start_ts) & (data.activity["ts"] < session.end_ts)
        ]
        assert (during["steps"] == 0).all()


def test_sick_day_has_illness_signature() -> None:
    sick = START + dt.timedelta(days=10)
    daily = generate(START, days=20, seed=3, sick_days={sick}).daily.set_index("date")
    others = daily.drop(index=sick)
    assert daily.loc[sick, "resting_hr"] > others["resting_hr"].mean() + 2
    assert daily.loc[sick, "hrv_rmssd_ms"] < others["hrv_rmssd_ms"].mean()
    assert daily.loc[sick, "skin_temp_delta_c"] > 0.4


def test_bedtime_is_near_local_evening() -> None:
    data = generate(START, days=10, tz="America/Toronto")
    local_hours = data.sleep_sessions["start_ts"].dt.tz_convert("America/Toronto").dt.hour
    assert local_hours.isin([21, 22, 23, 0, 1]).all()
