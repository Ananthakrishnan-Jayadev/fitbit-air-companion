import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from fitbit_app.ingest.timeutil import (
    floor_minute,
    parse_date,
    parse_duration_minutes,
    parse_offset,
    parse_ts,
    start_of_day_utc,
    to_civil_date,
    to_rfc3339,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-04-20T08:00:00Z", dt.datetime(2026, 4, 20, 8, tzinfo=dt.UTC)),
        ("2026-04-20T04:00:00-04:00", dt.datetime(2026, 4, 20, 8, tzinfo=dt.UTC)),
        (
            "2026-04-20T08:00:00.123456789Z",
            dt.datetime(2026, 4, 20, 8, 0, 0, 123456, tzinfo=dt.UTC),
        ),
    ],
)
def test_parse_ts(value: str, expected: dt.datetime) -> None:
    parsed = parse_ts(value)
    assert parsed == expected
    assert parsed.tzinfo == dt.UTC


def test_parse_ts_rejects_naive() -> None:
    with pytest.raises(ValueError):
        parse_ts("2026-04-20T08:00:00")


def test_parse_offset() -> None:
    assert parse_offset("-14400s") == dt.timedelta(hours=-4)
    assert parse_offset("0s") == dt.timedelta(0)
    assert parse_offset(None) == dt.timedelta(0)
    with pytest.raises(ValueError):
        parse_offset("-4h")


def test_parse_duration_minutes() -> None:
    assert parse_duration_minutes("3600s") == 60
    assert parse_duration_minutes("90.0s") == 1.5
    assert parse_duration_minutes(None) is None


def test_dates_round_trip() -> None:
    day = dt.date(2026, 10, 29)
    assert to_civil_date(day) == {"year": 2026, "month": 10, "day": 29}
    assert parse_date(to_civil_date(day)) == day
    assert start_of_day_utc(day) == dt.datetime(2026, 10, 29, tzinfo=dt.UTC)


def test_to_rfc3339_converts_to_utc() -> None:
    local = dt.datetime(2026, 10, 1, 8, 30, 15, 999, tzinfo=ZoneInfo("America/Toronto"))
    assert to_rfc3339(local) == "2026-10-01T12:30:15Z"


def test_floor_minute() -> None:
    ts = dt.datetime(2026, 10, 1, 8, 30, 59, 500, tzinfo=dt.UTC)
    assert floor_minute(ts) == dt.datetime(2026, 10, 1, 8, 30, tzinfo=dt.UTC)
