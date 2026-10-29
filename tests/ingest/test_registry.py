import datetime as dt

import pytest

from fitbit_app.ingest.registry import (
    FAST_KINDS,
    REGISTRY,
    SLOW_KINDS,
    DataTypeSpec,
    RecordKind,
    build_filter,
    select_specs,
)
from fitbit_app.ingest.scopes import READ_SCOPES

START = dt.datetime(2026, 10, 1, 4, 0, tzinfo=dt.UTC)
END = dt.datetime(2026, 10, 8, 4, 0, tzinfo=dt.UTC)


def _spec(key: str) -> DataTypeSpec:
    return next(s for s in REGISTRY if s.key == key)


def test_keys_are_unique() -> None:
    keys = [s.key for s in REGISTRY]
    assert len(keys) == len(set(keys))


def test_only_requested_read_scopes_are_used() -> None:
    assert {s.scope for s in REGISTRY} <= set(READ_SCOPES)


def test_rollup_ranges_fit_the_14_day_limit() -> None:
    for spec in REGISTRY:
        if spec.kind is RecordKind.ROLLUP:
            assert spec.chunk_days + 1 <= 14


def test_every_kind_is_scheduled() -> None:
    assert FAST_KINDS | SLOW_KINDS == set(RecordKind)


def test_heart_rate_is_typed_only() -> None:
    assert _spec("heart-rate").store_raw is False


def test_page_sizes() -> None:
    assert _spec("sleep").page_size == 25
    assert _spec("heart-rate").page_size == 10000


def test_beta_types_are_opt_in() -> None:
    assert "skin-temperature-sensors" not in {s.key for s in select_specs(include_beta=False)}
    assert "skin-temperature-sensors" in {s.key for s in select_specs(include_beta=True)}


def test_select_by_keys_and_kinds() -> None:
    specs = select_specs(include_beta=False, keys=["steps", "steps:daily", "sleep"])
    assert {s.key for s in specs} == {"steps", "steps:daily", "sleep"}
    slow = select_specs(include_beta=False, keys=["steps", "sleep"], kinds=SLOW_KINDS)
    assert [s.key for s in slow] == ["sleep"]


def test_unknown_key_raises() -> None:
    with pytest.raises(ValueError, match="nope"):
        select_specs(include_beta=False, keys=["steps", "nope"])


def test_filter_sample() -> None:
    assert build_filter(_spec("heart-rate"), START, END) == (
        'heartRate.sample_time.physical_time >= "2026-10-01T04:00:00Z" '
        'AND heartRate.sample_time.physical_time < "2026-10-08T04:00:00Z"'
    )


def test_filter_interval() -> None:
    assert build_filter(_spec("steps"), START, END) == (
        'steps.interval.start_time >= "2026-10-01T04:00:00Z" '
        'AND steps.interval.start_time < "2026-10-08T04:00:00Z"'
    )


def test_filter_daily_includes_end_day() -> None:
    assert build_filter(_spec("daily-resting-heart-rate"), START, END) == (
        'dailyRestingHeartRate.date >= "2026-10-01" AND dailyRestingHeartRate.date < "2026-10-09"'
    )


def test_filter_sleep_uses_end_time() -> None:
    assert build_filter(_spec("sleep"), START, END) == (
        'sleep.interval.end_time >= "2026-10-01T04:00:00Z" '
        'AND sleep.interval.end_time < "2026-10-08T04:00:00Z"'
    )


def test_filter_other_sessions_use_padded_civil_dates() -> None:
    assert build_filter(_spec("exercise"), START, END) == (
        'exercise.interval.civil_start_time >= "2026-09-30" '
        'AND exercise.interval.civil_start_time < "2026-10-09"'
    )


def test_rollups_have_no_filter() -> None:
    with pytest.raises(ValueError):
        build_filter(_spec("steps:daily"), START, END)
