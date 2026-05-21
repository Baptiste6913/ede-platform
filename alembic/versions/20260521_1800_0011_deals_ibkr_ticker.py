"""add deals.ibkr_ticker + deals.ibkr_exchange (Phase 8 ticker resolver cache)

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-21 18:00:00.000000

Phase 8 resolves each tradeable deal to an IBKR contract. The resolution
(symbol + exchange, or ISIN-derived) is cached on the deal so the daily
trading cron does not re-resolve every run and so operators can pin a
manual mapping. These are distinct from the existing `ticker_target`
(raw source ticker / ISIN from ingestion — e.g. DE deals carry the ISIN
there): `ibkr_ticker`/`ibkr_exchange` are the *broker-qualified* symbol and
IBKR exchange code (SBF / BVME / IBIS / SMART).

Nullable: a deal stays NULL until first resolved (or if it is not tradeable).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("ibkr_ticker", sa.Text(), nullable=True))
    op.add_column("deals", sa.Column("ibkr_exchange", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "ibkr_exchange")
    op.drop_column("deals", "ibkr_ticker")
