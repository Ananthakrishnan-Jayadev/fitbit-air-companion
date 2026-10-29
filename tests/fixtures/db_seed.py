"""Load SyntheticData into the database tables the score service reads."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from fitbit_app.storage.models import (
    ActivityMinute,
    DailyMetric,
    ExerciseSession,
    HrSample,
    HrvSample,
    SleepSession,
    SleepStage,
    Spo2Sample,
)
from fitbit_app.storage.types import utcnow
from fitbit_app.storage.upsert import upsert
from fixtures.synthetic import SyntheticData

# Synthetic levels -> Google's activityLevelType labels.
LEVELS = {
    "sedentary": "SEDENTARY",
    "light": "LIGHTLY_ACTIVE",
    "moderate": "MODERATELY_ACTIVE",
    "vigorous": "VERY_ACTIVE",
}


def seed(
    session_factory: sessionmaker[Session], data: SyntheticData, tz_offset_min: int = 0
) -> None:
    with session_factory() as session:
        upsert(
            session,
            HrSample,
            [
                {"ts": t.to_pydatetime(), "bpm": int(b)}
                for t, b in zip(data.hr.ts, data.hr.bpm, strict=True)
            ],
            index_elements=["ts"],
        )
        upsert(
            session,
            HrvSample,
            [
                {"ts": t.to_pydatetime(), "rmssd_ms": float(v)}
                for t, v in zip(data.hrv.ts, data.hrv.rmssd_ms, strict=True)
            ],
            index_elements=["ts"],
        )
        upsert(
            session,
            Spo2Sample,
            [
                {"ts": t.to_pydatetime(), "spo2_pct": float(v)}
                for t, v in zip(data.spo2.ts, data.spo2.spo2_pct, strict=True)
            ],
            index_elements=["ts"],
        )
        upsert(
            session,
            ActivityMinute,
            [
                {"ts": t.to_pydatetime(), "steps": int(s), "activity_level": LEVELS[str(level)]}
                for t, s, level in zip(
                    data.activity.ts,
                    data.activity.steps,
                    data.activity.activity_level,
                    strict=True,
                )
            ],
            index_elements=["ts"],
        )
        now = utcnow()
        upsert(
            session,
            DailyMetric,
            [
                {
                    "date": row.date,
                    "tz_offset_min": tz_offset_min,
                    "resting_hr": float(row.resting_hr),
                    "hrv_rmssd_ms": float(row.hrv_rmssd_ms),
                    "spo2_avg": float(row.spo2_avg),
                    "skin_temp_delta_c": float(row.skin_temp_delta_c),
                    "steps": int(row.steps),
                    "updated_at": now,
                }
                for row in data.daily.itertuples()
            ],
            index_elements=["date"],
        )
        for night in data.sleep_sessions.itertuples():
            sleep = SleepSession(
                source_key=f"synthetic-{night.session_id}",
                start_ts=night.start_ts.to_pydatetime(),
                end_ts=night.end_ts.to_pydatetime(),
                local_date=night.local_date,
                duration_min=float(night.duration_min),
                efficiency=None,
                is_main=True,
            )
            session.add(sleep)
            session.flush()
            stages = data.sleep_stages[data.sleep_stages.session_id == night.session_id]
            session.add_all(
                SleepStage(
                    session_id=sleep.id,
                    start_ts=stage.start_ts.to_pydatetime(),
                    end_ts=stage.end_ts.to_pydatetime(),
                    stage=stage.stage,
                )
                for stage in stages.itertuples()
            )
        for i, workout in enumerate(data.workouts.itertuples()):
            session.add(
                ExerciseSession(
                    source_key=f"synthetic-workout-{i}",
                    start_ts=workout.start_ts.to_pydatetime(),
                    end_ts=workout.end_ts.to_pydatetime(),
                    local_date=workout.local_date,
                    activity_type="RUNNING",
                    duration_min=45.0,
                )
            )
        session.commit()
