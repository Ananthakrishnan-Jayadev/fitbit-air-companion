"""Read helpers shared by the score service and the API. Sync: call from worker threads."""

from __future__ import annotations

import bisect
import datetime as dt
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fitbit_app.ingest.timeutil import parse_offset, parse_ts
from fitbit_app.storage.models import (
    ActivityMinute,
    DailyMetric,
    DataPoint,
    HrSample,
    HrvSample,
    Score,
    SleepSession,
    SleepStage,
    Spo2Sample,
    UserProfile,
)

DAILY_COLUMNS = [c.name for c in DailyMetric.__table__.columns if c.name != "date"]


@dataclass(frozen=True)
class Profile:
    age: int | None = None
    max_hr: int | None = None
    sleep_need_min: int | None = None


def load_profile(session: Session) -> Profile:
    row = session.get(UserProfile, 1)
    if row is None:
        return Profile()
    return Profile(row.age, row.max_hr, row.sleep_need_min)


# --- Local days --------------------------------------------------------------------------


class DayClock:
    """Maps local dates to UTC windows using per-day UTC offsets (from wake-up times).

    Days without a known offset use the nearest known day's offset, else UTC.
    """

    def __init__(self, offsets: dict[dt.date, int]) -> None:
        self._days = sorted(offsets)
        self._offsets = offsets

    @classmethod
    def load(cls, session: Session) -> DayClock:
        rows = session.execute(
            select(DailyMetric.date, DailyMetric.tz_offset_min).where(
                DailyMetric.tz_offset_min.is_not(None)
            )
        ).all()
        return cls({day: int(offset) for day, offset in rows})

    def offset(self, day: dt.date) -> dt.timedelta:
        if not self._days:
            return dt.timedelta(0)
        if day in self._offsets:
            return dt.timedelta(minutes=self._offsets[day])
        i = bisect.bisect_left(self._days, day)
        candidates = [self._days[j] for j in (i - 1, i) if 0 <= j < len(self._days)]
        nearest = min(candidates, key=lambda d: abs((d - day).days))
        return dt.timedelta(minutes=self._offsets[nearest])

    def window(self, day: dt.date) -> tuple[dt.datetime, dt.datetime]:
        """[local midnight, next local midnight) of `day`, in UTC."""
        start = dt.datetime.combine(day, dt.time(), tzinfo=dt.UTC) - self.offset(day)
        return start, start + dt.timedelta(days=1)

    def local_date(self, ts: dt.datetime) -> dt.date:
        utc_day = ts.astimezone(dt.UTC).date()
        return (ts + self.offset(utc_day)).date()


# --- Frames ------------------------------------------------------------------------------


def load_daily(session: Session, start: dt.date, end: dt.date) -> pd.DataFrame:
    """daily_metrics for [start, end], indexed by date (python `date`)."""
    rows = session.scalars(
        select(DailyMetric)
        .where(DailyMetric.date >= start, DailyMetric.date <= end)
        .order_by(DailyMetric.date)
    ).all()
    frame = pd.DataFrame(
        [{c: getattr(r, c) for c in DAILY_COLUMNS} for r in rows],
        index=pd.Index([r.date for r in rows], name="date"),
        columns=DAILY_COLUMNS,
    )
    return frame


def load_hr(session: Session, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
    rows = session.execute(
        select(HrSample.ts, HrSample.bpm)
        .where(HrSample.ts >= start, HrSample.ts < end)
        .order_by(HrSample.ts)
    ).all()
    return _frame(rows, ["ts", "bpm"])


def load_hrv(session: Session, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
    rows = session.execute(
        select(HrvSample.ts, HrvSample.rmssd_ms)
        .where(HrvSample.ts >= start, HrvSample.ts < end)
        .order_by(HrvSample.ts)
    ).all()
    return _frame(rows, ["ts", "rmssd_ms"])


def load_spo2(session: Session, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
    rows = session.execute(
        select(Spo2Sample.ts, Spo2Sample.spo2_pct)
        .where(Spo2Sample.ts >= start, Spo2Sample.ts < end)
        .order_by(Spo2Sample.ts)
    ).all()
    return _frame(rows, ["ts", "spo2_pct"])


def load_activity(session: Session, start: dt.datetime, end: dt.datetime) -> pd.DataFrame:
    rows = session.execute(
        select(
            ActivityMinute.ts,
            ActivityMinute.steps,
            ActivityMinute.activity_level,
            ActivityMinute.calories,
        )
        .where(ActivityMinute.ts >= start, ActivityMinute.ts < end)
        .order_by(ActivityMinute.ts)
    ).all()
    return _frame(rows, ["ts", "steps", "activity_level", "calories"])


def high_hr_quantile(session: Session, since: dt.datetime, quantile: float = 0.995) -> float | None:
    """Approximate high percentile of heart rate since `since`, computed in SQL."""
    count = session.scalar(select(func.count()).select_from(HrSample).where(HrSample.ts >= since))
    if not count:
        return None
    offset = int(count * (1 - quantile))
    return session.scalar(
        select(HrSample.bpm)
        .where(HrSample.ts >= since)
        .order_by(HrSample.bpm.desc())
        .offset(offset)
        .limit(1)
    )


# --- Sleep -------------------------------------------------------------------------------


def main_sleep(session: Session, day: dt.date) -> SleepSession | None:
    """The night that ended on local `day`: the main session, else the longest."""
    sessions = session.scalars(select(SleepSession).where(SleepSession.local_date == day)).all()
    if not sessions:
        return None
    return max(sessions, key=lambda s: (s.is_main, s.duration_min))


def sleep_stages(session: Session, session_id: int) -> pd.DataFrame:
    rows = session.execute(
        select(SleepStage.start_ts, SleepStage.end_ts, SleepStage.stage)
        .where(SleepStage.session_id == session_id)
        .order_by(SleepStage.start_ts)
    ).all()
    return _frame(rows, ["start_ts", "end_ts", "stage"])


def sleep_intervals(
    session: Session, start: dt.datetime, end: dt.datetime
) -> list[tuple[dt.datetime, dt.datetime]]:
    """All sleep sessions overlapping [start, end)."""
    rows = session.execute(
        select(SleepSession.start_ts, SleepSession.end_ts).where(
            SleepSession.end_ts > start, SleepSession.start_ts < end
        )
    ).all()
    return [(s, e) for s, e in rows]


def scored_strain(session: Session, start: dt.date, end: dt.date) -> dict[dt.date, float | None]:
    rows = session.execute(
        select(Score.date, Score.strain).where(Score.date >= start, Score.date <= end)
    ).all()
    return {day: strain for day, strain in rows}


def sedentary_periods(
    session: Session, start: dt.datetime, end: dt.datetime
) -> list[tuple[dt.datetime, dt.datetime, dt.timedelta]]:
    """Sedentary periods (start, end, UTC offset) starting in [start, end), from raw JSON."""
    rows = session.scalars(
        select(DataPoint.value_json).where(
            DataPoint.data_type == "sedentary-period",
            DataPoint.start_ts >= start,
            DataPoint.start_ts < end,
        )
    ).all()
    periods = []
    for value in rows:
        interval = value.get("sedentaryPeriod", {}).get("interval", {})
        if "startTime" in interval and "endTime" in interval:
            periods.append(
                (
                    parse_ts(interval["startTime"]),
                    parse_ts(interval["endTime"]),
                    parse_offset(interval.get("startUtcOffset")),
                )
            )
    return periods


def _frame(rows: list, columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame([tuple(r) for r in rows], columns=columns)
    for column in columns:
        if column == "ts" or column.endswith("_ts"):
            frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame
