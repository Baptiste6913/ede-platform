"""phase_09c_deal_consideration_pricing

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-25 15:00:00.000000

Phase 9.1c — structured consideration + external (yfinance) pricing.

- Convert deals.offer_price_quality_flag from the 0014 Postgres ENUM to TEXT +
  CHECK (adds 'verified_mixed'). TEXT is cheaper to evolve than an ENUM
  (decision P9.1c); the value list lives in src.core.enums.
- deals.offer_price_total_eur NUMERIC(12,4) NULL — economic value of a mixed
  offer (cash + share legs), recomputed via a yfinance acquirer quote.
- deals.pricing_source TEXT NOT NULL DEFAULT 'parser_only' + CHECK.
- deal_consideration — 1:1 structured cash/share legs + acquirer (audit trail).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from src.core import enums

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUM_NAME = "offer_price_quality_flag_enum"
_DEFAULT_FLAG = "suspect_low_unverified"
# The 0014 value set (pre-verified_mixed) — used to recreate the ENUM on downgrade.
_ORIGINAL_FLAGS = (
    "verified_cash",
    "suspect_mixed",
    "suspect_low_unverified",
    "failed_validation",
    "manual_review",
)


def _in_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # 1. offer_price_quality_flag: ENUM -> TEXT + CHECK; drop the unused type.
    op.execute("ALTER TABLE deals ALTER COLUMN offer_price_quality_flag DROP DEFAULT")
    op.execute(
        "ALTER TABLE deals ALTER COLUMN offer_price_quality_flag "
        "TYPE TEXT USING offer_price_quality_flag::text"
    )
    op.execute(
        f"ALTER TABLE deals ALTER COLUMN offer_price_quality_flag SET DEFAULT '{_DEFAULT_FLAG}'"
    )
    op.execute(f"DROP TYPE {_ENUM_NAME}")
    op.create_check_constraint(
        "ck_deals_offer_price_quality_flag",
        "deals",
        f"offer_price_quality_flag IN ({_in_list(enums.OFFER_PRICE_QUALITY_FLAGS)})",
    )

    # 2. Mixed-offer total + pricing provenance.
    op.add_column("deals", sa.Column("offer_price_total_eur", sa.Numeric(12, 4), nullable=True))
    op.add_column(
        "deals",
        sa.Column("pricing_source", sa.Text(), nullable=False, server_default="parser_only"),
    )
    op.create_check_constraint(
        "ck_deals_pricing_source",
        "deals",
        f"pricing_source IN ({_in_list(enums.PRICING_SOURCES)})",
    )

    # 3. deal_consideration — 1:1 structured legs.
    op.create_table(
        "deal_consideration",
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("cash_eur", sa.Numeric(12, 4), nullable=True),
        sa.Column("share_ratio", sa.Numeric(12, 6), nullable=True),
        sa.Column("acquirer_isin", sa.Text(), nullable=True),
        sa.Column("acquirer_ticker_yf", sa.Text(), nullable=True),
        sa.Column("source_clause_excerpt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("deal_consideration")
    op.drop_constraint("ck_deals_pricing_source", "deals", type_="check")
    op.drop_column("deals", "pricing_source")
    op.drop_column("deals", "offer_price_total_eur")

    # Guard: 'verified_mixed' (added by 0015) is absent from the 0014 enum, so
    # the ::enum cast below would PG-error opaquely. Fail loudly with an
    # actionable message instead.
    conn = op.get_bind()
    count = conn.execute(
        sa.text("SELECT COUNT(*) FROM deals WHERE offer_price_quality_flag = 'verified_mixed'")
    ).scalar()
    if count:
        raise RuntimeError(
            f"Cannot downgrade 0015->0014: {count} deal(s) carry 'verified_mixed', "
            "absent from the 0014 enum. Reset them to 'suspect_mixed' first."
        )

    # Revert offer_price_quality_flag: TEXT + CHECK -> 0014 ENUM.
    op.drop_constraint("ck_deals_offer_price_quality_flag", "deals", type_="check")
    op.execute(f"CREATE TYPE {_ENUM_NAME} AS ENUM ({_in_list(_ORIGINAL_FLAGS)})")
    op.execute("ALTER TABLE deals ALTER COLUMN offer_price_quality_flag DROP DEFAULT")
    op.execute(
        f"ALTER TABLE deals ALTER COLUMN offer_price_quality_flag "
        f"TYPE {_ENUM_NAME} USING offer_price_quality_flag::{_ENUM_NAME}"
    )
    op.execute(
        f"ALTER TABLE deals ALTER COLUMN offer_price_quality_flag "
        f"SET DEFAULT '{_DEFAULT_FLAG}'::{_ENUM_NAME}"
    )
