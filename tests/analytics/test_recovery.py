import pytest

from fitbit_app.analytics.recovery import RecoveryInput, recovery_score


def test_average_day_is_about_fifty() -> None:
    result = recovery_score(RecoveryInput(hrv_z=0, rhr_z=0, resp_z=0, sleep_perf=50))
    assert result.score == 50


def test_good_day_beats_bad_day() -> None:
    good = recovery_score(RecoveryInput(hrv_z=1.5, rhr_z=-1, sleep_perf=90)).score
    bad = recovery_score(RecoveryInput(hrv_z=-1.5, rhr_z=1.5, sleep_perf=40)).score
    assert good is not None and bad is not None
    assert good > 70 > 40 > bad


def test_needs_hrv_or_resting_hr() -> None:
    assert recovery_score(RecoveryInput(sleep_perf=90, resp_z=0)).score is None
    assert recovery_score(RecoveryInput(rhr_z=0)).score == 50


def test_missing_components_are_renormalized() -> None:
    only_hrv = recovery_score(RecoveryInput(hrv_z=1)).score
    assert only_hrv == pytest.approx(70)


def test_penalties() -> None:
    base = RecoveryInput(hrv_z=0, rhr_z=0, sleep_perf=50)
    fever = recovery_score(RecoveryInput(hrv_z=0, rhr_z=0, sleep_perf=50, temp_delta_c=0.7))
    low_spo2 = recovery_score(RecoveryInput(hrv_z=0, rhr_z=0, sleep_perf=50, spo2_z=-2.5))
    assert recovery_score(base).score == 50
    assert fever.score == 40
    assert fever.penalties == {"temperature": 10.0}
    assert low_spo2.score == 45


def test_score_is_clipped() -> None:
    assert recovery_score(RecoveryInput(hrv_z=10, rhr_z=-10, sleep_perf=100)).score == 100
    worst = RecoveryInput(hrv_z=-10, rhr_z=10, sleep_perf=0, temp_delta_c=1.0)
    assert recovery_score(worst).score == 0
