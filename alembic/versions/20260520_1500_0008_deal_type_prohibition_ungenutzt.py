"""add prohibition_ungenutzt to deal_type_enum (Phase 6 Step-0 extension)

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-20 15:00:00.000000

The Phase-6 Step-0 24-month backfill extension surfaces the need to
ingest the BaFin "Untersagung" rows (§15 WpÜG regulatory prohibitions).
They were silently dropped at discovery in phase-5 (tech debt #2). To
keep them as first-class rows in `deals`, we add a dedicated enum value
so the existing `deal_type` NOT-NULL contract still holds.

The value name preserves the German legal label suffix `_ungenutzt`
(literally: "the offer process was unused/halted") to disambiguate from
any future generic `prohibition` value other regulators might warrant.

Like migration 0007, this `ALTER TYPE ... ADD VALUE` runs in an
`autocommit_block()` (Postgres requires ENUM mutation outside the outer
migration transaction). `IF NOT EXISTS` (PG 9.6+) makes it idempotent.
Downgrade is a documented no-op: PG has no `DROP VALUE`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE deal_type_enum ADD VALUE IF NOT EXISTS 'prohibition_ungenutzt'")


def downgrade() -> None:
    # PostgreSQL cannot DROP an ENUM value once added without a destructive
    # rename/recreate dance. Leave downgrade as a documented no-op; any real
    # rollback need should be a dedicated forward migration.
    pass
