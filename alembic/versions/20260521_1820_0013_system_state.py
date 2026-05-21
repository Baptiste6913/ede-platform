"""create system_state table (Phase 8 safeguards: ramp-up, daily baseline, cooldown)

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-21 18:20:00.000000

A tiny key/value store for trading runtime state that must survive restarts:
ramp-up validated count, the day's NetLiquidation baseline (daily-loss limit),
and the last-order timestamp (cooldown). The kill switch itself is a file
(`data/kill_switch.flag`, gitignored) so it can be flipped without a DB write.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_state",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("system_state")
