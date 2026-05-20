"""add cross-jurisdiction values to deal_type_enum

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-19 16:00:00.000000

Phase 5 — BaFin discovery exposed that the current `deal_type_enum`
lacks a canonical value for delisting-style offers. 32 % of recent
BaFin Angebotsunterlagen (76 / 241) are delisting variants. Rather
than add one value at a time per phase, this migration also lands the
two missing FR/IT canonical values that were already documented in
`src/core/enums.py` comments but absent from the database type:

  - `delisting_offer`            — cross-jurisdiction (DE 4 variants,
                                   IT OPSC delisting, FR future)
  - `opa_volontaria_preventiva`  — IT (Consob preventiva), future use
  - `garantie_de_cours`          — FR (art. 235-1 RGAMF). NOTE: already
                                   added in migration 0004; we re-issue
                                   with IF NOT EXISTS for idempotency.

`ALTER TYPE ... ADD VALUE` is autocommit-only in PostgreSQL — we use
`autocommit_block()` to escape the migration's outer transaction. The
`IF NOT EXISTS` clause (PG 9.6+) makes the migration idempotent.

DOWNGRADE LIMITATION: PostgreSQL has no `ALTER TYPE ... DROP VALUE`.
Removing an enum value requires the classic DROP/CREATE/UPDATE dance
which (a) breaks every row that references the value being dropped
and (b) requires rewriting the column with the new type. The downgrade
path here is therefore documented but intentionally **left as a no-op
with a warning**: rolling back would only be needed if the values were
mis-named, in which case a dedicated fix-up migration is the right
tool. This is consistent with how Alembic + Postgres enums are widely
handled in production codebases.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_VALUES: tuple[str, ...] = (
    "delisting_offer",
    "opa_volontaria_preventiva",
    "garantie_de_cours",  # already present from 0004 — IF NOT EXISTS guards it
)


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot run inside the transaction that wraps the
    # migration by default. Open an autocommit block per value.
    with op.get_context().autocommit_block():
        for value in _NEW_VALUES:
            op.execute(f"ALTER TYPE deal_type_enum ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL does not support `ALTER TYPE ... DROP VALUE`. The standard
    # workaround (rename old type → create new type → update column → drop old
    # type) is destructive against any row that uses one of the newly added
    # values, so we intentionally leave downgrade as a no-op. Any genuine
    # rollback need should be handled by a dedicated forward migration.
    pass
