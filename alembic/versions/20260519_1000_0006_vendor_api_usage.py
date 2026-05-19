"""create vendor_api_usage table for monthly budget enforcement

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-19 10:00:00.000000

Phase 4 — Consob via ScrapingBee.

Tracks per-vendor monthly credit consumption so the poller can refuse new
calls before exceeding the free-tier budget. Schema is generic so future
vendors (Bright Data, ZenRows, OpenAI, Anthropic) can reuse it.

One row per (vendor, year_month, request_id). For accounting:
    SELECT vendor, year_month, sum(credits_cost) AS used_credits
    FROM vendor_api_usage
    WHERE vendor = 'scrapingbee'
    GROUP BY vendor, year_month;
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vendor_api_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("vendor", sa.String(length=32), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),  # 'YYYY-MM'
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("request_url", sa.Text(), nullable=True),
        sa.Column("target_url", sa.Text(), nullable=True),
        sa.Column("credits_cost", sa.Integer(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.CheckConstraint("credits_cost >= 0", name="ck_vendor_api_usage_cost_nonneg"),
    )
    op.create_index(
        "ix_vendor_api_usage_vendor_month",
        "vendor_api_usage",
        ["vendor", "year_month"],
    )
    op.create_index(
        "ix_vendor_api_usage_ts",
        "vendor_api_usage",
        ["ts"],
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_api_usage_ts", table_name="vendor_api_usage")
    op.drop_index("ix_vendor_api_usage_vendor_month", table_name="vendor_api_usage")
    op.drop_table("vendor_api_usage")
