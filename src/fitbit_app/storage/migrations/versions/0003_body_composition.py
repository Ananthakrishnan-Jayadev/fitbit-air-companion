"""Daily weight and body fat columns.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("daily_metrics") as batch:
        batch.add_column(sa.Column("weight_kg", sa.Float(), nullable=True))
        batch.add_column(sa.Column("body_fat_pct", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_metrics") as batch:
        batch.drop_column("body_fat_pct")
        batch.drop_column("weight_kg")
