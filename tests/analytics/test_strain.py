import datetime as dt

import pandas as pd
import pytest

from fitbit_app.analytics.strain import (
    MAX_STRAIN,
    day_strain,
    estimate_max_hr,
    strain_from_trimp,
    strain_target,
    trimp,
)

T0 = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.UTC)


def _hr(bpms: list[int], every_s: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": [T0 + dt.timedelta(seconds=i * every_s) for i in range(len(bpms))],
            "bpm": bpms,
        }
    )


def test_resting_heart_rate_adds_no_load() -> None:
    load, minutes = trimp(_hr([60] * 720), resting_hr=60, max_hr=190)
    assert load == 0
    assert minutes == 0


def test_hard_effort_adds_more_load_than_easy() -> None:
    easy, _ = trimp(_hr([110] * 720), resting_hr=60, max_hr=190)
    hard, _ = trimp(_hr([160] * 720), resting_hr=60, max_hr=190)
    assert 0 < easy < hard


def test_one_hour_at_70_percent_reserve() -> None:
    # HRr = 0.7 -> 60 * 0.7 * 0.64 * e^(1.344) ~= 103
    load, minutes = trimp(_hr([151] * 721, every_s=5), resting_hr=60, max_hr=190)
    assert minutes == pytest.approx(60, abs=0.5)
    assert load == pytest.approx(103, rel=0.03)


def test_gaps_are_capped() -> None:
    gappy = pd.DataFrame({"ts": [T0, T0 + dt.timedelta(hours=3)], "bpm": [160, 160]})
    _, minutes = trimp(gappy, resting_hr=60, max_hr=190)
    assert minutes <= 2  # never 3 hours


def test_invalid_max_hr() -> None:
    with pytest.raises(ValueError):
        trimp(_hr([100, 100]), resting_hr=60, max_hr=55)


def test_strain_scale() -> None:
    assert strain_from_trimp(0) == 0
    assert strain_from_trimp(400) == MAX_STRAIN
    assert strain_from_trimp(10_000) == MAX_STRAIN
    assert 0 < strain_from_trimp(30) < strain_from_trimp(100) < MAX_STRAIN


def test_day_strain() -> None:
    result = day_strain(_hr([150] * 720), resting_hr=60, max_hr=190)
    assert 10 < result.strain < 21
    assert result.minutes_counted == pytest.approx(60, abs=0.5)


@pytest.mark.parametrize(
    ("age", "profile_max", "observed", "expected"),
    [
        (30, 185, 175.0, (185.0, "profile")),
        (30, None, 175.0, (187.0, "age")),
        (None, None, 150.0, (170.0, "observed")),
        (None, None, 199.0, (199.0, "observed")),
        (None, None, None, (190.0, "default")),
    ],
)
def test_estimate_max_hr(
    age: int | None,
    profile_max: int | None,
    observed: float | None,
    expected: tuple[float, str],
) -> None:
    assert estimate_max_hr(age, profile_max, observed) == expected


@pytest.mark.parametrize(
    ("recovery", "target"),
    [(80, (14.0, 18.0)), (50, (10.0, 14.0)), (20, (6.0, 10.0)), (None, None)],
)
def test_strain_target(recovery: float | None, target: tuple[float, float] | None) -> None:
    assert strain_target(recovery) == target
