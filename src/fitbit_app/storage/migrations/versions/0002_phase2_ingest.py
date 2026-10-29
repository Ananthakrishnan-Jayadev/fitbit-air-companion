"""Phase 2: ingest bookkeeping, HR motion context, respiratory rate, user profile.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("oauth_tokens") as batch:
        batch.add_column(sa.Column("health_user_id", sa.String(63), nullable=True))
        batch.add_column(
            sa.Column("needs_reauth", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("sync_state") as batch:
        batch.add_column(sa.Column("synced_from", sa.DateTime(), nullable=True))
    with op.batch_alter_table("hr_samples") as batch:
        batch.add_column(sa.Column("motion_context", sa.String(32), nullable=True))
    with op.batch_alter_table("daily_metrics") as batch:
        batch.add_column(sa.Column("respiratory_rate", sa.Float(), nullable=True))
    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("max_hr", sa.Integer(), nullable=True),
        sa.Column("sleep_need_min", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_profile")),
    )


def downgrade() -> None:
    op.drop_table("user_profile")
    with op.batch_alter_table("daily_metrics") as batch:
        batch.drop_column("respiratory_rate")
    with op.batch_alter_table("hr_samples") as batch:
        batch.drop_column("motion_context")
    with op.batch_alter_table("sync_state") as batch:
        batch.drop_column("synced_from")
    with op.batch_alter_table("oauth_tokens") as batch:
        batch.drop_column("needs_reauth")
        batch.drop_column("health_user_id")
