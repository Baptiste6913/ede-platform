"""phase_11_reference_price_premium

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-02 12:00:00.000000

Phase 11 — reference-price provenance for the premium_pct backfill.

The ``premium_pct`` column already exists (migration 0002, Numeric(7,4), stored
as a *fraction* — scoring multiplies by 100). This migration adds the
provenance columns the Phase-10 closure deferred, so a populated premium_pct is
auditable end-to-end:

- reference_price_at_announcement NUMERIC(12,4) — close (EUR) at T-1.
- reference_price_source TEXT — pipeline that produced it (e.g. openfigi+yfinance).
- reference_price_target_date DATE — announcement_date - 1 business day (requested).
- reference_price_effective_date DATE — the actual trading day yfinance returned.
- ticker_resolution_flag TEXT — OpenFIGI resolution / backfill outcome
  (home_venue / home_venue_growth / venue_fallback / no_match / unknown_exch /
  no_price_data / premium_out_of_bounds / manual_review). No CHECK constraint:
  the value set spans resolution provenance + processing outcomes and is
  expected to evolve.

All columns are nullable — a deal that does not resolve / price simply leaves
them NULL with the reason in ticker_resolution_flag.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "deals",
        sa.Column("reference_price_at_announcement", sa.Numeric(12, 4), nullable=True),
    )
    op.add_column("deals", sa.Column("reference_price_source", sa.Text(), nullable=True))
    op.add_column("deals", sa.Column("reference_price_target_date", sa.Date(), nullable=True))
    op.add_column("deals", sa.Column("reference_price_effective_date", sa.Date(), nullable=True))
    op.add_column("deals", sa.Column("ticker_resolution_flag", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "ticker_resolution_flag")
    op.drop_column("deals", "reference_price_effective_date")
    op.drop_column("deals", "reference_price_target_date")
    op.drop_column("deals", "reference_price_source")
    op.drop_column("deals", "reference_price_at_announcement")
