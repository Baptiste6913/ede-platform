"""add completion_label columns to deals (Phase 6 scoring V1)

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-20 17:00:00.000000

Phase 6 scoring engine training set — the operator's labelled CSV
(`artifacts/phase-06/deals_labelled.csv`) drives ground truth for the
logistic regression. We persist the labels on `deals` so the scoring
pipeline can train on a single SQL join (no external label file at
inference time).

Three columns:
  - `completion_label` SMALLINT NULL  (1=closed, 0=failed, NULL=pending)
  - `completion_label_source` TEXT NULL  (URL / freeform note)
  - `completion_label_date` TIMESTAMPTZ NULL  (when the label was applied)

A partial index on `completion_label IS NOT NULL` accelerates training
queries (~130 labelled / ~700 total filings).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "deals",
        sa.Column("completion_label", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "deals",
        sa.Column("completion_label_source", sa.Text(), nullable=True),
    )
    op.add_column(
        "deals",
        sa.Column(
            "completion_label_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_deals_completion_label_binary",
        "deals",
        "completion_label IS NULL OR completion_label IN (0, 1)",
    )
    op.create_index(
        "ix_deals_completion_label_labelled",
        "deals",
        ["completion_label"],
        postgresql_where=sa.text("completion_label IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_deals_completion_label_labelled", table_name="deals")
    op.drop_constraint("ck_deals_completion_label_binary", "deals", type_="check")
    op.drop_column("deals", "completion_label_date")
    op.drop_column("deals", "completion_label_source")
    op.drop_column("deals", "completion_label")
