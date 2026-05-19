"""cleanup legacy AMF-SYN-* synthetic-ref deals from phase 2

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-14 09:00:00.000000

Phase 4bis — closes phase-2 tech debt item #1.

Phase 2's RSS poller (display/23 = Communiqués AMF, not the BDIF filings
feed) created deal rows with a synthetic `regulator_ref` of the form
`AMF-SYN-{sha256(title|published_date)[:24]}` because canonical AMF refs
weren't present in those RSS items. Phase 3's `BdifPoller` replaced the
RSS-as-source-of-deals semantics — RSS is now event-only — so any
`AMF-SYN-*` row that survived is **noise** that pollutes downstream
scoring / analytics.

This migration deletes them. Cascading FK on `events.deal_id` /
`scores.deal_id` / `analyses.deal_id` / `paper_positions.deal_id`
(ON DELETE CASCADE per migrations 0002 + 0003) handles the related rows
automatically.

**Defensive design**: the migration is a no-op when no synthetic rows
exist (e.g. on `ede_test` in CI, or a fresh `ede` DB). It only ever
deletes rows whose `regulator_ref` matches the well-defined
`AMF-SYN-%` pattern.

Reversibility: this is a **data-only** migration. `downgrade()` cannot
restore the deleted rows from inside Alembic. Recovery path: load the
pre-cleanup pg_dump from `artifacts/phase-04bis/backup-pre-cleanup-*.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Count before — observable in `alembic upgrade head` output.
    count = conn.execute(
        text("SELECT count(*) FROM deals WHERE regulator_ref LIKE 'AMF-SYN-%'")
    ).scalar_one()
    if count == 0:
        # No-op path — nothing to clean.
        return

    # Delete the deals. CASCADE deletes related events, scores, analyses,
    # paper_positions automatically.
    conn.execute(text("DELETE FROM deals WHERE regulator_ref LIKE 'AMF-SYN-%'"))


def downgrade() -> None:
    # Data-only migration: no schema change to revert. Restoring the deleted
    # rows requires loading `artifacts/phase-04bis/backup-pre-cleanup-*.sql`
    # manually:
    #
    #   docker compose exec -T postgres psql -U ede -d ede \
    #     < artifacts/phase-04bis/backup-pre-cleanup-<timestamp>.sql
    #
    # (Recreates ALL rows that were in the DB at backup time — review before
    # applying.)
    pass
