"""create trades table (Phase 8 order lifecycle + idempotency)

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-21 18:10:00.000000

`trades` is the order-execution ledger, distinct from `paper_positions`
(current position state, migration 0002): one row per submitted order with a
status machine PENDING → SUBMITTED → FILLED / REJECTED / CANCELLED.

Idempotency: `trade_id` (UUID string) is UNIQUE — re-submitting the same
TradeRequest is a no-op. `deal_id` references the representative deal of the
collapsed cluster (mirrors `scores.deal_id`); the brief's illustrative
`cluster_id → deals_clusters(id)` is adapted to the real schema where clusters
are implicit.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUSES = "'PENDING','SUBMITTED','FILLED','REJECTED','CANCELLED'"


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trade_id", sa.String(36), nullable=False),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("stop_loss_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("take_profit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("ibkr_order_id", sa.String(32), nullable=True),
        sa.Column("ibkr_stop_order_id", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("filled_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("filled_quantity", sa.Integer(), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pnl_realized", sa.Numeric(14, 2), nullable=True),
        sa.Column("pnl_unrealized", sa.Numeric(14, 2), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("trade_id", name="uq_trades_trade_id"),
        sa.CheckConstraint("quantity > 0", name="ck_trades_quantity_positive"),
        sa.CheckConstraint("side IN ('BUY','SELL')", name="ck_trades_side"),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name="ck_trades_status"),
    )
    op.create_index("ix_trades_status", "trades", ["status"])
    op.create_index("ix_trades_deal_id", "trades", ["deal_id"])


def downgrade() -> None:
    op.drop_index("ix_trades_deal_id", table_name="trades")
    op.drop_index("ix_trades_status", table_name="trades")
    op.drop_table("trades")
