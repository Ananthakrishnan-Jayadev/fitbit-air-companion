"""ScoreService: runs the pure analytics for each local day and stores the results.

Days are processed oldest first, because baselines and training load depend on earlier days.
Writes `scores`, `baselines`, derived `daily_metrics` columns (sleep_min, sedentary_min) and
`exercise_sessions.max_hr`.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.analytics.activity import sedentary_minutes_by_day
from fitbit_app.analytics.anomaly import detect_anomalies
from fitbit_app.analytics.baselines import (
    BASELINE_METRICS,
    WINDOW_DAYS,
    Baseline,
    compute_baselines,
    zscore,
)
from fitbit_app.analytics.load import acute_chronic_ratio, load_flag
from fitbit_app.analytics.recovery import RecoveryInput, recovery_score
from fitbit_app.analytics.sleep import (
    DEFAULT_SLEEP_NEED_MIN,
    SleepNight,
    SleepScore,
    minutes_since_evening,
    sleep_performance,
)
from fitbit_app.analytics.strain import StrainResult, day_strain, estimate_max_hr, strain_target
from fitbit_app.analytics.stress import DailyStress, daily_stress, stress_timeline
from fitbit_app.storage import models
from fitbit_app.storage.models import (
    DailyMetric,
    ExerciseSession,
    HrSample,
    Score,
    SleepSession,
)
from fitbit_app.storage.queries import (
    DayClock,
    Profile,
    high_hr_quantile,
    load_activity,
    load_daily,
    load_hr,
    load_profile,
    main_sleep,
    scored_strain,
    sedentary_periods,
    sleep_intervals,
    sleep_stages,
)
from fitbit_app.storage.types import utcnow
from fitbit_app.storage.upsert import upsert

logger = logging.getLogger(__name__)

# Recompute this many recent days after each sync (Google revises recent sleep/daily values).
RECENT_DAYS = 4
# Days of history loaded before the first scored day (baselines need 30, load needs 28).
HISTORY_DAYS = WINDOW_DAYS + 10
CONSISTENCY_NIGHTS = 7
MIN_HR_SAMPLES = 60
OBSERVED_MAX_HR_DAYS = 30


@dataclass
class _Context:
    daily: pd.DataFrame
    profile: Profile
    clock: DayClock
    max_hr: float
    max_hr_method: str
    sedentary: dict[dt.date, float]
    strain: dict[dt.date, float | None] = field(default_factory=dict)
    hrv_z: dict[dt.date, float | None] = field(default_factory=dict)

    def value(self, day: dt.date, column: str) -> float | None:
        if day not in self.daily.index or column not in self.daily.columns:
            return None
        v = self.daily.at[day, column]
        return None if pd.isna(v) else float(v)

    def set_value(self, day: dt.date, column: str, value: float) -> None:
        self.daily.loc[day, column] = value


class ScoreService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        clock: Callable[[], dt.datetime] = utcnow,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def recompute_after_sync(self) -> int:
        """Everything on the first run; afterwards the last few days (Google revises them)
        plus any day with data but no score yet, e.g. a gap while the app was closed."""
        available = self._data_days()
        with self._session_factory() as session:
            scored = set(session.scalars(select(Score.date)).all())
        if not scored:
            return self.recompute(available)
        unscored = [day for day in available if day not in scored]
        return self.recompute([*available[-RECENT_DAYS:], *unscored])

    def recompute_all(self) -> int:
        return self.recompute(self._data_days())

    def recompute_recent(self, days: int = RECENT_DAYS) -> int:
        available = self._data_days()
        return self.recompute(available[-days:])

    def recompute(self, days: Iterable[dt.date]) -> int:
        ordered = sorted(set(days))
        if not ordered:
            return 0
        with self._session_factory() as session:
            ctx = self._context(session, ordered[0], ordered[-1])
            scored = sum(self._score_day(session, ctx, day) for day in ordered)
            self._update_exercise_max_hr(session, ctx, ordered[0], ordered[-1])
            session.commit()
        logger.info(
            "Scored %d of %d days (%s .. %s)", scored, len(ordered), ordered[0], ordered[-1]
        )
        return scored

    # --- Setup ---------------------------------------------------------------------------

    def _data_days(self) -> list[dt.date]:
        """Local days that have any daily or sleep data, up to today."""
        with self._session_factory() as session:
            daily = set(session.scalars(select(DailyMetric.date)).all())
            sleep = set(session.scalars(select(SleepSession.local_date)).all())
            clock = DayClock.load(session)
        today = clock.local_date(self._clock())
        return sorted(day for day in daily | sleep if day <= today)

    def _context(self, session: Session, first: dt.date, last: dt.date) -> _Context:
        clock = DayClock.load(session)
        profile = load_profile(session)
        now = self._clock()
        observed = high_hr_quantile(session, now - dt.timedelta(days=OBSERVED_MAX_HR_DAYS))
        max_hr, method = estimate_max_hr(profile.age, profile.max_hr, observed)

        history_start = first - dt.timedelta(days=HISTORY_DAYS)
        window_start, _ = clock.window(history_start)
        _, window_end = clock.window(last)
        sedentary = sedentary_minutes_by_day(
            (s, e, o) for s, e, o in sedentary_periods(session, window_start, window_end)
        )
        ctx = _Context(
            daily=load_daily(session, history_start, last),
            profile=profile,
            clock=clock,
            max_hr=max_hr,
            max_hr_method=method,
            sedentary=sedentary,
            strain=scored_strain(session, history_start, last),
        )
        # HRV z-scores of the two days before the range, for the 3-day suppression streak.
        for back in (2, 1):
            day = first - dt.timedelta(days=back)
            ctx.hrv_z[day] = zscore(
                ctx.value(day, "hrv_rmssd_ms"),
                compute_baselines(ctx.daily, day).get("hrv_rmssd_ms"),
            )
        return ctx

    # --- One day -------------------------------------------------------------------------

    def _score_day(self, session: Session, ctx: _Context, day: dt.date) -> bool:
        start, end = ctx.clock.window(day)

        sleep = self._sleep(session, ctx, day)
        if sleep is not None:
            ctx.set_value(day, "sleep_min", round(sleep.asleep_min, 1))
        if day in ctx.sedentary:
            ctx.set_value(day, "sedentary_min", ctx.sedentary[day])

        baselines = compute_baselines(ctx.daily, day)
        z = {m: zscore(ctx.value(day, m), baselines.get(m)) for m in BASELINE_METRICS}
        temp_delta = ctx.value(day, "skin_temp_delta_c")
        recovery = recovery_score(
            RecoveryInput(
                hrv_z=z["hrv_rmssd_ms"],
                rhr_z=z["resting_hr"],
                resp_z=z["respiratory_rate"],
                spo2_z=z["spo2_avg"],
                temp_delta_c=temp_delta,
                sleep_perf=sleep.score if sleep else None,
            )
        )

        resting = ctx.value(day, "resting_hr")
        if resting is None and "resting_hr" in baselines:
            resting = baselines["resting_hr"].typical
        hr = load_hr(session, start, end)
        strain: StrainResult | None = None
        stress: DailyStress | None = None
        if resting is not None and len(hr) >= MIN_HR_SAMPLES:
            if ctx.max_hr > resting:
                strain = day_strain(hr, resting, ctx.max_hr)
            activity = load_activity(session, start, end)
            asleep = sleep_intervals(session, start, end)
            stress = daily_stress(stress_timeline(hr, activity, resting, asleep))

        has_data = day in ctx.daily.index or sleep is not None or not hr.empty
        if not has_data:
            return False

        recent_hrv = [ctx.hrv_z.get(day - dt.timedelta(days=k)) for k in (2, 1)]
        anomalies = detect_anomalies(
            hrv_z=z["hrv_rmssd_ms"],
            rhr_z=z["resting_hr"],
            resp_z=z["respiratory_rate"],
            spo2_z=z["spo2_avg"],
            temp_delta_c=temp_delta,
            recent_hrv_z=recent_hrv,
        )
        ctx.hrv_z[day] = z["hrv_rmssd_ms"]
        ctx.strain[day] = strain.strain if strain else None
        ratio = acute_chronic_ratio(ctx.strain, day)
        flags = list(anomalies.flags)
        if (flag := load_flag(ratio)) is not None:
            flags.append(flag)
        target = strain_target(recovery.score)

        now = utcnow()
        upsert(
            session,
            Score,
            [
                {
                    "date": day,
                    "recovery": recovery.score,
                    "sleep_perf": sleep.score if sleep else None,
                    "strain": strain.strain if strain else None,
                    "strain_target_low": target[0] if target else None,
                    "strain_target_high": target[1] if target else None,
                    "stress_avg": stress.average if stress else None,
                    "illness_risk": anomalies.illness_risk,
                    "components_json": _json_safe(
                        {
                            "sleep": _sleep_components(sleep),
                            "recovery": {
                                "components": recovery.components,
                                "penalties": recovery.penalties,
                            },
                            "strain": _strain_components(strain, resting, ctx),
                            "stress": _stress_components(stress),
                            "z": z,
                            "flags": flags,
                            "acwr": ratio,
                        }
                    ),
                    "computed_at": now,
                }
            ],
            index_elements=["date"],
        )
        self._store_baselines(session, day, baselines)
        upsert(
            session,
            DailyMetric,
            [
                {
                    "date": day,
                    "sleep_min": ctx.value(day, "sleep_min"),
                    "sedentary_min": _round_int(ctx.value(day, "sedentary_min")),
                    "updated_at": now,
                }
            ],
            index_elements=["date"],
        )
        return True

    def _sleep(self, session: Session, ctx: _Context, day: dt.date) -> SleepScore | None:
        night = main_sleep(session, day)
        if night is None:
            return None
        bedtimes = []
        for back in range(CONSISTENCY_NIGHTS - 1, -1, -1):
            other_day = day - dt.timedelta(days=back)
            other = night if back == 0 else main_sleep(session, other_day)
            if other is not None:
                local_start = other.start_ts + ctx.clock.offset(other_day)
                bedtimes.append(minutes_since_evening(local_start))
        return sleep_performance(
            SleepNight(
                start=night.start_ts,
                end=night.end_ts,
                duration_min=night.duration_min,
                efficiency=night.efficiency,
                stages=sleep_stages(session, night.id),
            ),
            need_min=ctx.profile.sleep_need_min or DEFAULT_SLEEP_NEED_MIN,
            bedtimes=bedtimes,
        )

    @staticmethod
    def _store_baselines(session: Session, day: dt.date, baselines: dict[str, Baseline]) -> None:
        upsert(
            session,
            models.Baseline,
            [
                {
                    "metric": b.metric,
                    "as_of": day,
                    "window_days": WINDOW_DAYS,
                    "mean": b.mean,
                    "sd": b.sd,
                    "n": b.n,
                }
                for b in baselines.values()
            ],
            index_elements=["metric", "as_of", "window_days"],
        )

    @staticmethod
    def _update_exercise_max_hr(
        session: Session, ctx: _Context, first: dt.date, last: dt.date
    ) -> None:
        """The API has no workout max HR; take it from our heart-rate samples."""
        workouts = session.scalars(
            select(ExerciseSession).where(
                ExerciseSession.local_date >= first, ExerciseSession.local_date <= last
            )
        ).all()
        for workout in workouts:
            peak = session.scalar(
                select(func.max(HrSample.bpm)).where(
                    HrSample.ts >= workout.start_ts, HrSample.ts < workout.end_ts
                )
            )
            workout.max_hr = float(peak) if peak is not None else None


def _sleep_components(sleep: SleepScore | None) -> dict[str, Any] | None:
    if sleep is None:
        return None
    return {
        "components": sleep.components,
        "asleep_min": sleep.asleep_min,
        "stage_minutes": sleep.stage_minutes,
    }


def _strain_components(
    strain: StrainResult | None, resting: float | None, ctx: _Context
) -> dict[str, Any] | None:
    if strain is None:
        return None
    return {
        "trimp": strain.trimp,
        "minutes_counted": strain.minutes_counted,
        "resting_hr": resting,
        "max_hr": ctx.max_hr,
        "max_hr_method": ctx.max_hr_method,
    }


def _stress_components(stress: DailyStress | None) -> dict[str, Any] | None:
    if stress is None:
        return None
    return {"high_minutes": stress.high_minutes, "valid_minutes": stress.valid_minutes}


def _round_int(value: float | None) -> int | None:
    return None if value is None else round(value)


def _json_safe(value: Any) -> Any:
    """Plain JSON types only: no NaN/inf, no numpy scalars; floats rounded."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return int(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return None if math.isnan(number) or math.isinf(number) else round(number, 3)
