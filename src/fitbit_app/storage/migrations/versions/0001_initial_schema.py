"""Initial schema (project.md §6).

Revision ID: 0001
Revises:
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(32), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_tokens")),
    )
    op.create_table(
        "sync_state",
        sa.Column("data_type", sa.String(64), nullable=False),
        sa.Column("cursor", sa.DateTime(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("earliest_seen_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("data_type", name=op.f("pk_sync_state")),
    )
    op.create_table(
        "data_points",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data_type", sa.String(64), nullable=False),
        sa.Column("start_ts", sa.DateTime(), nullable=False),
        sa.Column("end_ts", sa.DateTime(), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_points")),
        sa.UniqueConstraint(
            "data_type",
            "start_ts",
            "end_ts",
            "source_id",
            name=op.f("uq_data_points_data_type_start_ts_end_ts_source_id"),
        ),
    )
    op.create_table(
        "hr_samples",
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("bpm", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("ts", name=op.f("pk_hr_samples")),
    )
    op.create_table(
        "hrv_samples",
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("rmssd_ms", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("ts", name=op.f("pk_hrv_samples")),
    )
    op.create_table(
        "spo2_samples",
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("spo2_pct", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("ts", name=op.f("pk_spo2_samples")),
    )
    op.create_table(
        "activity_minutes",
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("activity_level", sa.String(32), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("ts", name=op.f("pk_activity_minutes")),
    )
    op.create_table(
        "sleep_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("start_ts", sa.DateTime(), nullable=False),
        sa.Column("end_ts", sa.DateTime(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("duration_min", sa.Float(), nullable=False),
        sa.Column("efficiency", sa.Float(), nullable=True),
        sa.Column("is_main", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sleep_sessions")),
        sa.UniqueConstraint("source_key", name=op.f("uq_sleep_sessions_source_key")),
    )
    op.create_index(
        op.f("ix_sleep_sessions_local_date"), "sleep_sessions", ["local_date"], unique=False
    )
    op.create_table(
        "sleep_stages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("start_ts", sa.DateTime(), nullable=False),
        sa.Column("end_ts", sa.DateTime(), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sleep_sessions.id"],
            name=op.f("fk_sleep_stages_session_id_sleep_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sleep_stages")),
    )
    op.create_index(
        op.f("ix_sleep_stages_session_id"), "sleep_stages", ["session_id"], unique=False
    )
    op.create_table(
        "exercise_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("start_ts", sa.DateTime(), nullable=False),
        sa.Column("end_ts", sa.DateTime(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("activity_type", sa.String(64), nullable=False),
        sa.Column("duration_min", sa.Float(), nullable=False),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("avg_hr", sa.Float(), nullable=True),
        sa.Column("max_hr", sa.Float(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("zones_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_sessions")),
        sa.UniqueConstraint("source_key", name=op.f("uq_exercise_sessions_source_key")),
    )
    op.create_index(
        op.f("ix_exercise_sessions_local_date"), "exercise_sessions", ["local_date"], unique=False
    )
    op.create_table(
        "daily_metrics",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("tz_offset_min", sa.Integer(), nullable=True),
        sa.Column("resting_hr", sa.Float(), nullable=True),
        sa.Column("hrv_rmssd_ms", sa.Float(), nullable=True),
        sa.Column("spo2_avg", sa.Float(), nullable=True),
        sa.Column("spo2_min", sa.Float(), nullable=True),
        sa.Column("skin_temp_delta_c", sa.Float(), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("active_zone_minutes", sa.Integer(), nullable=True),
        sa.Column("active_calories", sa.Float(), nullable=True),
        sa.Column("total_calories", sa.Float(), nullable=True),
        sa.Column("sedentary_min", sa.Integer(), nullable=True),
        sa.Column("sleep_min", sa.Float(), nullable=True),
        sa.Column("vo2_max", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("date", name=op.f("pk_daily_metrics")),
    )
    op.create_table(
        "baselines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("sd", sa.Float(), nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_baselines")),
        sa.UniqueConstraint(
            "metric", "as_of", "window_days", name=op.f("uq_baselines_metric_as_of_window_days")
        ),
    )
    op.create_table(
        "scores",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("recovery", sa.Float(), nullable=True),
        sa.Column("sleep_perf", sa.Float(), nullable=True),
        sa.Column("strain", sa.Float(), nullable=True),
        sa.Column("strain_target_low", sa.Float(), nullable=True),
        sa.Column("strain_target_high", sa.Float(), nullable=True),
        sa.Column("stress_avg", sa.Float(), nullable=True),
        sa.Column("illness_risk", sa.Float(), nullable=True),
        sa.Column("components_json", sa.JSON(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("date", name=op.f("pk_scores")),
    )
    op.create_table(
        "journal_entries",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("date", name=op.f("pk_journal_entries")),
    )
    op.create_table(
        "ai_insights",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_insights")),
        sa.UniqueConstraint(
            "date", "kind", "prompt_hash", name=op.f("uq_ai_insights_date_kind_prompt_hash")
        ),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(
        op.f("ix_chat_messages_conversation_id"), "chat_messages", ["conversation_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_messages_conversation_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("ai_insights")
    op.drop_table("journal_entries")
    op.drop_table("scores")
    op.drop_table("baselines")
    op.drop_table("daily_metrics")
    op.drop_index(op.f("ix_exercise_sessions_local_date"), table_name="exercise_sessions")
    op.drop_table("exercise_sessions")
    op.drop_index(op.f("ix_sleep_stages_session_id"), table_name="sleep_stages")
    op.drop_table("sleep_stages")
    op.drop_index(op.f("ix_sleep_sessions_local_date"), table_name="sleep_sessions")
    op.drop_table("sleep_sessions")
    op.drop_table("activity_minutes")
    op.drop_table("spo2_samples")
    op.drop_table("hrv_samples")
    op.drop_table("hr_samples")
    op.drop_table("data_points")
    op.drop_table("sync_state")
    op.drop_table("oauth_tokens")
