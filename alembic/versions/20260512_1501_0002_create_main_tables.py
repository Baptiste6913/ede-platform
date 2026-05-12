"""create main tables (deals, events, scores, analyses, paper_positions)

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12 15:01:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# References to enum types created in 0001 — we declare them with
# create_type=False so alembic does NOT try to CREATE TYPE again.
def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    # ---- deals ---------------------------------------------------------
    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("juridiction", _enum("jurisdiction_enum"), nullable=False),
        sa.Column("regulator_ref", sa.String(length=128), nullable=False),
        sa.Column("ticker_target", sa.String(length=32), nullable=True),
        sa.Column("ticker_acquirer", sa.String(length=32), nullable=True),
        sa.Column("target_name", sa.String(length=255), nullable=False),
        sa.Column("acquirer_name", sa.String(length=255), nullable=False),
        sa.Column("announcement_date", sa.Date(), nullable=False),
        sa.Column("deal_type", _enum("deal_type_enum"), nullable=False),
        sa.Column("status", _enum("deal_status_enum"), nullable=False),
        sa.Column("offer_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", _enum("currency_enum"), nullable=True),
        sa.Column("payment_cash_share", sa.Numeric(5, 4), nullable=True),
        sa.Column("premium_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column("min_acceptance_threshold", sa.Numeric(5, 4), nullable=True),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "juridiction",
            "regulator_ref",
            name="uq_deals_juridiction_regulator_ref",
        ),
    )
    op.create_index("ix_deals_juridiction_status", "deals", ["juridiction", "status"])
    op.create_index("ix_deals_ticker_target", "deals", ["ticker_target"])

    # ---- events --------------------------------------------------------
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", _enum("event_type_enum"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_events_deal_id_ts", "events", ["deal_id", "ts"])
    op.create_index("ix_events_event_type", "events", ["event_type"])

    # ---- scores --------------------------------------------------------
    op.create_table(
        "scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("p_completion", sa.Numeric(6, 5), nullable=False),
        sa.Column("p_market_implied", sa.Numeric(6, 5), nullable=True),
        sa.Column("edge", sa.Numeric(7, 5), nullable=True),
        sa.Column("expected_return_annualized", sa.Numeric(8, 5), nullable=True),
        sa.Column("decision", _enum("decision_enum"), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "p_completion >= 0 AND p_completion <= 1",
            name="ck_scores_p_completion",
        ),
        sa.CheckConstraint(
            "p_market_implied IS NULL OR (p_market_implied >= 0 AND p_market_implied <= 1)",
            name="ck_scores_p_market_implied",
        ),
    )
    op.create_index("ix_scores_deal_id_ts", "scores", ["deal_id", "ts"])

    # ---- analyses ------------------------------------------------------
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", _enum("analyst_source_enum"), nullable=False),
        sa.Column("brief_path", sa.Text(), nullable=True),
        sa.Column("verdict", _enum("analyst_verdict_enum"), nullable=False),
        sa.Column("thesis_md", sa.Text(), nullable=True),
        sa.Column("risks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("catalysts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_analyses_deal_id_ts", "analyses", ["deal_id", "ts"])

    # ---- paper_positions ----------------------------------------------
    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "open_ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("close_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("exit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("size_eur", sa.Numeric(14, 2), nullable=False),
        sa.Column("side", _enum("position_side_enum"), nullable=False),
        sa.Column("pnl_eur", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", _enum("position_status_enum"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("size_eur > 0", name="ck_paper_positions_size_eur_positive"),
    )
    op.create_index("ix_paper_positions_deal_id", "paper_positions", ["deal_id"])
    op.create_index("ix_paper_positions_status", "paper_positions", ["status"])


def downgrade() -> None:
    op.drop_table("paper_positions")
    op.drop_table("analyses")
    op.drop_table("scores")
    op.drop_table("events")
    op.drop_table("deals")
