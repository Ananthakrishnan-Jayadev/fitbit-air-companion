import datetime as dt

from fitbit_app.analytics.body import change_since, latest, split_mass

D = dt.date(2026, 10, 31)


def _p(days_ago: int, value: float) -> tuple[dt.date, float]:
    return D - dt.timedelta(days=days_ago), value


def test_latest() -> None:
    assert latest([_p(3, 80.0), _p(0, 79.0), _p(1, 79.5)]) == (D, 79.0)
    assert latest([]) is None


def test_change_uses_most_recent_reading_at_least_n_days_back() -> None:
    points = [_p(40, 82.0), _p(31, 81.0), _p(8, 80.0), _p(2, 79.6), _p(0, 79.0)]
    assert change_since(points, 7) == -1.0  # vs day -8
    assert change_since(points, 30) == -2.0  # vs day -31


def test_change_needs_history() -> None:
    assert change_since([_p(3, 80.0), _p(0, 79.0)], 7) is None
    assert change_since([], 7) is None


def test_split_mass() -> None:
    assert split_mass(80.0, 20.0) == (16.0, 64.0)
