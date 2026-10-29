"""Which Google Health data types we sync, and how.

Source: https://developers.google.com/health/data-types (verified 2026-10-29).
To enable another type, add one DataTypeSpec here; storage and normalization pick it up
(raw JSON is always kept unless `store_raw=False`).

Filter field prefixes are the snake_case form of the union field (`heart_rate`,
`daily_resting_heart_rate`). The docs show `dailyHeartRateVariability.date`, but the live API
rejects camelCase for multi-word types with INVALID_DATA_POINT_FILTER_DATA_TYPE_RESTRICTION
(observed 2026-10-29); single-word types (`steps`, `sleep`) work either way.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from fitbit_app.ingest import scopes
from fitbit_app.ingest.timeutil import to_rfc3339


class RecordKind(StrEnum):
    SAMPLE = "sample"
    INTERVAL = "interval"
    SESSION = "session"
    DAILY = "daily"
    ROLLUP = "rollup"


class Method(StrEnum):
    RECONCILE = "reconcile"
    LIST = "list"
    DAILY_ROLLUP = "dailyRollUp"


class Family(StrEnum):
    WEARABLES = "google-wearables"  # Google/Fitbit trackers, no manual logs
    GOOGLE = "google-sources"  # also manual logs and Health Connect


@dataclass(frozen=True)
class DataTypeSpec:
    name: str  # URL identifier, e.g. "heart-rate"
    field: str  # JSON union field and filter prefix, e.g. "heartRate"
    kind: RecordKind
    scope: str
    method: Method = Method.RECONCILE
    family: Family = Family.WEARABLES
    version: str = "v4"
    chunk_days: int = 7
    store_raw: bool = True
    beta: bool = False

    @property
    def key(self) -> str:
        """Unique id for sync state and raw storage (rollups share names with list types)."""
        return f"{self.name}:daily" if self.kind is RecordKind.ROLLUP else self.name

    @property
    def filter_prefix(self) -> str:
        """heartRate -> heart_rate, runVo2Max -> run_vo2_max."""
        return _CAMEL_BOUNDARY.sub("_", self.field).lower()

    @property
    def page_size(self) -> int:
        # Sessions: default and max are both 25. Everything else: max 10000.
        return 25 if self.kind is RecordKind.SESSION else 10000


_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")

_AF = scopes.ACTIVITY_AND_FITNESS
_HM = scopes.HEALTH_METRICS
_S, _I, _D, _R = RecordKind.SAMPLE, RecordKind.INTERVAL, RecordKind.DAILY, RecordKind.ROLLUP

REGISTRY: tuple[DataTypeSpec, ...] = (
    # Samples
    # 1-second resolution: ~86k points/day, so 1-day chunks and no raw JSON copy.
    DataTypeSpec("heart-rate", "heartRate", _S, _HM, chunk_days=1, store_raw=False),
    DataTypeSpec("heart-rate-variability", "heartRateVariability", _S, _HM),
    DataTypeSpec("oxygen-saturation", "oxygenSaturation", _S, _HM),
    DataTypeSpec("respiratory-rate-sleep-summary", "respiratoryRateSleepSummary", _S, _HM),
    DataTypeSpec("vo2-max", "vo2Max", _S, _AF, chunk_days=30),
    DataTypeSpec("run-vo2-max", "runVo2Max", _S, _AF, chunk_days=30),
    DataTypeSpec("weight", "weight", _S, _HM, family=Family.GOOGLE, chunk_days=30),
    DataTypeSpec("body-fat", "bodyFat", _S, _HM, family=Family.GOOGLE, chunk_days=30),
    # Intervals
    DataTypeSpec("steps", "steps", _I, _AF),
    DataTypeSpec("distance", "distance", _I, _AF),
    DataTypeSpec("active-energy-burned", "activeEnergyBurned", _I, _AF),
    DataTypeSpec("activity-level", "activityLevel", _I, _AF),
    DataTypeSpec("active-zone-minutes", "activeZoneMinutes", _I, _AF),
    DataTypeSpec("sedentary-period", "sedentaryPeriod", _I, _AF),
    DataTypeSpec("active-minutes", "activeMinutes", _I, _AF),
    DataTypeSpec("time-in-heart-rate-zone", "timeInHeartRateZone", _I, _AF),
    # Sessions
    DataTypeSpec("sleep", "sleep", RecordKind.SESSION, scopes.SLEEP),
    DataTypeSpec("exercise", "exercise", RecordKind.SESSION, _AF),
    DataTypeSpec(
        "irregular-rhythm-notification",
        "irregularRhythmNotification",
        RecordKind.SESSION,
        scopes.IRN,
        method=Method.LIST,  # the only supported read method
        chunk_days=30,
    ),
    # Daily summaries
    DataTypeSpec("daily-resting-heart-rate", "dailyRestingHeartRate", _D, _HM, chunk_days=30),
    DataTypeSpec(
        "daily-heart-rate-variability", "dailyHeartRateVariability", _D, _HM, chunk_days=30
    ),
    DataTypeSpec("daily-oxygen-saturation", "dailyOxygenSaturation", _D, _HM, chunk_days=30),
    DataTypeSpec("daily-respiratory-rate", "dailyRespiratoryRate", _D, _HM, chunk_days=30),
    DataTypeSpec(
        "daily-sleep-temperature-derivations",
        "dailySleepTemperatureDerivations",
        _D,
        _HM,
        chunk_days=30,
    ),
    DataTypeSpec("daily-vo2-max", "dailyVo2Max", _D, _AF, chunk_days=30),
    DataTypeSpec("daily-heart-rate-zones", "dailyHeartRateZones", _D, _HM, chunk_days=30),
    # Daily rollups (Google handles DST/travel). Range limit is 14 days for total-calories,
    # so 13-day chunks plus the partial current day stay within it.
    DataTypeSpec("steps", "steps", _R, _AF, method=Method.DAILY_ROLLUP, chunk_days=13),
    DataTypeSpec("distance", "distance", _R, _AF, method=Method.DAILY_ROLLUP, chunk_days=13),
    DataTypeSpec(
        "total-calories", "totalCalories", _R, _AF, method=Method.DAILY_ROLLUP, chunk_days=13
    ),
    DataTypeSpec(
        "active-energy-burned",
        "activeEnergyBurned",
        _R,
        _AF,
        method=Method.DAILY_ROLLUP,
        chunk_days=13,
    ),
    DataTypeSpec(
        "active-zone-minutes",
        "activeZoneMinutes",
        _R,
        _AF,
        method=Method.DAILY_ROLLUP,
        chunk_days=13,
    ),
    # v4beta (opt-in via ENABLE_BETA_TYPES)
    DataTypeSpec(
        "skin-temperature-sensors", "skinTemperatureSensors", _S, _HM, version="v4beta", beta=True
    ),
)

# Polled often (intraday); the rest change slowly and are polled hourly.
FAST_KINDS = frozenset({RecordKind.SAMPLE, RecordKind.INTERVAL})
SLOW_KINDS = frozenset({RecordKind.SESSION, RecordKind.DAILY, RecordKind.ROLLUP})


def select_specs(
    *,
    include_beta: bool,
    keys: Iterable[str] | None = None,
    kinds: Iterable[RecordKind] | None = None,
) -> list[DataTypeSpec]:
    """Registry entries filtered by key and kind. Unknown keys raise ValueError."""
    specs = [s for s in REGISTRY if include_beta or not s.beta]
    if keys is not None:
        wanted = set(keys)
        unknown = wanted - {s.key for s in specs}
        if unknown:
            raise ValueError(f"Unknown data types: {', '.join(sorted(unknown))}")
        specs = [s for s in specs if s.key in wanted]
    if kinds is not None:
        kind_set = set(kinds)
        specs = [s for s in specs if s.kind in kind_set]
    return specs


def build_filter(spec: DataTypeSpec, start: dt.datetime, end: dt.datetime) -> str:
    """AIP-160 filter for [start, end). See the `list` method reference for field names."""
    f = spec.filter_prefix
    if spec.kind is RecordKind.SAMPLE:
        return _range(f"{f}.sample_time.physical_time", to_rfc3339(start), to_rfc3339(end))
    if spec.kind is RecordKind.INTERVAL:
        return _range(f"{f}.interval.start_time", to_rfc3339(start), to_rfc3339(end))
    if spec.kind is RecordKind.DAILY:
        # Daily summaries are keyed by civil date; include the (partial) end day.
        last = (end + dt.timedelta(days=1)).date()
        return _range(f"{f}.date", start.date().isoformat(), last.isoformat())
    if spec.name == "sleep":
        # Sleep only supports filtering on end time.
        return _range("sleep.interval.end_time", to_rfc3339(start), to_rfc3339(end))
    if spec.kind is RecordKind.SESSION:
        # Other sessions filter on civil (local) start time; pad a day for timezones.
        first = (start - dt.timedelta(days=1)).date()
        last = (end + dt.timedelta(days=1)).date()
        return _range(f"{f}.interval.civil_start_time", first.isoformat(), last.isoformat())
    raise ValueError(f"{spec.key} is fetched with dailyRollUp, not a filter")


def _range(field: str, lower: str, upper: str) -> str:
    return f'{field} >= "{lower}" AND {field} < "{upper}"'
