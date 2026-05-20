"""extend scores table with Phase 6 V1 fields

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-20 17:01:00.000000

The existing `scores` table from migration 0002 stored
`p_completion + p_market_implied + edge + expected_return_annualized
+ decision + model_version + features`. The Phase 6 V1 scoring engine
needs three additional fields:

  - `score_stars` SMALLINT  — 1..5 derived from p_completion
  - `risk_factors` JSONB    — top-3 negative coefficients x feature values
  - `positive_factors` JSONB — top-3 positive coefficients x feature values

We also relax `decision NOT NULL → NULLABLE`: V1 only assigns a decision
for `enter` / `wait` / `skip` thresholds at scoring time, but legacy
seed data may not have one.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scores",
        sa.Column("score_stars", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "scores",
        sa.Column(
            "risk_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "scores",
        sa.Column(
            "positive_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_scores_score_stars_range",
        "scores",
        "score_stars IS NULL OR score_stars BETWEEN 1 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint("ck_scores_score_stars_range", "scores", type_="check")
    op.drop_column("scores", "positive_factors")
    op.drop_column("scores", "risk_factors")
    op.drop_column("scores", "score_stars")
