"""phase_09a_offer_price_quality_flag

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-25 10:10:01.786459+00:00

Phase 9.1a — minimal schema for the BaFin offer_price parser fix.

Two columns on `deals`:
  - `offer_price_quality_flag` ENUM — provenance/confidence of `offer_price`
    after the re-anchored parser (see src/core/enums.OFFER_PRICE_QUALITY_FLAGS).
    Defaults to 'suspect_low_unverified' so every existing row is explicitly
    "not yet re-validated" until the P9.1a backfill re-parses it.
  - `parser_version` SMALLINT — bumped to 2 by the P9.1a re-parse so future
    backfills can target stale rows (`parser_version < N`).

The enum type is created/dropped manually (the ORM uses create_type=False),
matching the convention in migration 0001.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from src.core import enums

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUM_NAME = "offer_price_quality_flag_enum"
_DEFAULT_FLAG = "suspect_low_unverified"


def upgrade() -> None:
    values_sql = ", ".join(f"'{v}'" for v in enums.OFFER_PRICE_QUALITY_FLAGS)
    op.execute(f"CREATE TYPE {_ENUM_NAME} AS ENUM ({values_sql})")
    op.add_column(
        "deals",
        sa.Column(
            "offer_price_quality_flag",
            postgresql.ENUM(
                *enums.OFFER_PRICE_QUALITY_FLAGS,
                name=_ENUM_NAME,
                create_type=False,
            ),
            nullable=False,
            server_default=_DEFAULT_FLAG,
        ),
    )
    op.add_column(
        "deals",
        sa.Column(
            "parser_version",
            sa.SmallInteger(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("deals", "parser_version")
    op.drop_column("deals", "offer_price_quality_flag")
    op.execute(f"DROP TYPE IF EXISTS {_ENUM_NAME}")
