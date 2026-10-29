"""SQLAlchemy models (project.md §6). Every change here needs an Alembic migration."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fitbit_app.storage.types import UTCDateTime, utcnow

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        dt.datetime: UTCDateTime(),
        dt.date: Date(),
        dict[str, Any]: JSON(),
        list[str]: JSON(),
    }


# --- Auth & sync bookkeeping -------------------------------------------------------------


class OAuthToken(Base):
    """Google OAuth tokens. Single row (id=1)."""

    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    token_type: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[dt.datetime]
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class SyncState(Base):
    """Per-data-type sync cursor and last outcome."""

    __tablename__ = "sync_state"

    data_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    cursor: Mapped[dt.datetime | None]
    last_attempt_at: Mapped[dt.datetime | None]
    last_success_at: Mapped[dt.datetime | None]
    last_error_at: Mapped[dt.datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    earliest_seen_at: Mapped[dt.datetime | None]


class DataPoint(Base):
    """Raw landing table: every API data point, stored losslessly."""

    __tablename__ = "data_points"
    __table_args__ = (UniqueConstraint("data_type", "start_ts", "end_ts", "source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_type: Mapped[str] = mapped_column(String(64))
    start_ts: Mapped[dt.datetime]
    end_ts: Mapped[dt.datetime]
    source_id: Mapped[str] = mapped_column(String(255), default="")
    value_json: Mapped[dict[str, Any]]
    ingested_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


# --- Typed intraday series ---------------------------------------------------------------


class HrSample(Base):
    __tablename__ = "hr_samples"

    ts: Mapped[dt.datetime] = mapped_column(primary_key=True)
    bpm: Mapped[int] = mapped_column(Integer)


class HrvSample(Base):
    __tablename__ = "hrv_samples"

    ts: Mapped[dt.datetime] = mapped_column(primary_key=True)
    rmssd_ms: Mapped[float] = mapped_column(Float)


class Spo2Sample(Base):
    __tablename__ = "spo2_samples"

    ts: Mapped[dt.datetime] = mapped_column(primary_key=True)
    spo2_pct: Mapped[float] = mapped_column(Float)


class ActivityMinute(Base):
    __tablename__ = "activity_minutes"

    ts: Mapped[dt.datetime] = mapped_column(primary_key=True)
    steps: Mapped[int | None] = mapped_column(Integer)
    activity_level: Mapped[str | None] = mapped_column(String(32))
    calories: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float)


# --- Sessions ----------------------------------------------------------------------------


class SleepSession(Base):
    __tablename__ = "sleep_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(255), unique=True)
    start_ts: Mapped[dt.datetime]
    end_ts: Mapped[dt.datetime]
    # Local date of waking up; the "night of" belongs to this day.
    local_date: Mapped[dt.date] = mapped_column(index=True)
    duration_min: Mapped[float] = mapped_column(Float)
    efficiency: Mapped[float | None] = mapped_column(Float)
    is_main: Mapped[bool] = mapped_column(Boolean, default=True)


class SleepStage(Base):
    __tablename__ = "sleep_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sleep_sessions.id", ondelete="CASCADE"), index=True
    )
    start_ts: Mapped[dt.datetime]
    end_ts: Mapped[dt.datetime]
    stage: Mapped[str] = mapped_column(String(16))


class ExerciseSession(Base):
    __tablename__ = "exercise_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(255), unique=True)
    start_ts: Mapped[dt.datetime]
    end_ts: Mapped[dt.datetime]
    local_date: Mapped[dt.date] = mapped_column(index=True)
    activity_type: Mapped[str] = mapped_column(String(64))
    duration_min: Mapped[float] = mapped_column(Float)
    calories: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[float | None] = mapped_column(Float)
    max_hr: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float)
    zones_json: Mapped[dict[str, Any] | None]


# --- Daily aggregates & derived ----------------------------------------------------------


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    date: Mapped[dt.date] = mapped_column(primary_key=True)
    tz_offset_min: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[float | None] = mapped_column(Float)
    hrv_rmssd_ms: Mapped[float | None] = mapped_column(Float)
    spo2_avg: Mapped[float | None] = mapped_column(Float)
    spo2_min: Mapped[float | None] = mapped_column(Float)
    skin_temp_delta_c: Mapped[float | None] = mapped_column(Float)
    steps: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    active_zone_minutes: Mapped[int | None] = mapped_column(Integer)
    active_calories: Mapped[float | None] = mapped_column(Float)
    total_calories: Mapped[float | None] = mapped_column(Float)
    sedentary_min: Mapped[int | None] = mapped_column(Integer)
    sleep_min: Mapped[float | None] = mapped_column(Float)
    vo2_max: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Baseline(Base):
    __tablename__ = "baselines"
    __table_args__ = (UniqueConstraint("metric", "as_of", "window_days"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric: Mapped[str] = mapped_column(String(64))
    as_of: Mapped[dt.date]
    window_days: Mapped[int] = mapped_column(Integer)
    mean: Mapped[float] = mapped_column(Float)
    sd: Mapped[float] = mapped_column(Float)
    n: Mapped[int] = mapped_column(Integer)


class Score(Base):
    __tablename__ = "scores"

    date: Mapped[dt.date] = mapped_column(primary_key=True)
    recovery: Mapped[float | None] = mapped_column(Float)
    sleep_perf: Mapped[float | None] = mapped_column(Float)
    strain: Mapped[float | None] = mapped_column(Float)
    strain_target_low: Mapped[float | None] = mapped_column(Float)
    strain_target_high: Mapped[float | None] = mapped_column(Float)
    stress_avg: Mapped[float | None] = mapped_column(Float)
    illness_risk: Mapped[float | None] = mapped_column(Float)
    components_json: Mapped[dict[str, Any] | None]
    computed_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


# --- User input & AI ---------------------------------------------------------------------


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    date: Mapped[dt.date] = mapped_column(primary_key=True)
    tags: Mapped[list[str]] = mapped_column(default=list)
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[dt.datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class AIInsight(Base):
    __tablename__ = "ai_insights"
    __table_args__ = (UniqueConstraint("date", "kind", "prompt_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[dt.date]
    kind: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    prompt_hash: Mapped[str] = mapped_column(String(64))
    content_json: Mapped[dict[str, Any]]
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
