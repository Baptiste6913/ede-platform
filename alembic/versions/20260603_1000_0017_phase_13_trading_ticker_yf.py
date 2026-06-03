"""add deals.trading_ticker_yf (Phase 13 — decision-time price provider)

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-03 10:00:00.000000

Phase 13 decouples decision calculation from IBKR: the reference price now comes
from a non-broker provider (yfinance EOD close). That provider keys on the
**Yahoo** ticker (e.g. ``COVH.PA``), which is distinct from the broker-qualified
``ibkr_ticker`` (``COVH``) / ``ibkr_exchange`` (``SBF``) added in 0011.

The OpenFIGI resolver (Phase 11) already computes this Yahoo ticker but only
persisted ``ticker_resolution_flag`` + ``reference_price_*`` (0016) — the ticker
itself was discarded. This column persists it so a deal can be priced (and a
decision produced) without re-resolving every cycle.

Nullable: NULL until first resolved, or when the ISIN does not resolve to a
priceable venue (the reason then lives in ``ticker_resolution_flag``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("trading_ticker_yf", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "trading_ticker_yf")
