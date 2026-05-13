"""Tests for migration 0005 (cleanup AMF-SYN-* legacy rows).

Two scenarios:
- **No-op**: against a clean DB (no AMF-SYN-* rows), upgrade is a no-op
  and downgrade is a no-op.
- **With data**: pre-seed AMF-SYN-* deals + related events; upgrade
  deletes them via FK CASCADE; un-related rows are preserved.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Deal, Event

pytestmark = pytest.mark.integration


async def _count_amf_syn(session: AsyncSession) -> int:
    result = await session.execute(
        text("SELECT count(*) FROM deals WHERE regulator_ref LIKE 'AMF-SYN-%'")
    )
    return int(result.scalar_one())


async def _count_orphan_events(session: AsyncSession) -> int:
    result = await session.execute(
        text(
            "SELECT count(*) FROM events e "
            "LEFT JOIN deals d ON d.id = e.deal_id "
            "WHERE d.id IS NULL"
        )
    )
    return int(result.scalar_one())


def _delete_amf_syn_sql() -> str:
    """Replays exactly what migration 0005 does in its upgrade() body."""
    return "DELETE FROM deals WHERE regulator_ref LIKE 'AMF-SYN-%'"


async def test_cleanup_is_noop_on_clean_db(db_session: AsyncSession) -> None:
    """Fresh ede_test has no AMF-SYN rows — migration deletes nothing."""
    assert await _count_amf_syn(db_session) == 0

    await db_session.execute(text(_delete_amf_syn_sql()))
    await db_session.commit()

    assert await _count_amf_syn(db_session) == 0
    assert await _count_orphan_events(db_session) == 0


async def test_cleanup_deletes_synthetic_rows_and_cascades_events(
    db_session: AsyncSession,
) -> None:
    """Pre-seed an AMF-SYN deal + 2 events + 1 legit deal; cleanup removes
    only the synthetic deal and its events."""
    # Legit BDIF-sourced deal that must survive
    legit = Deal(
        juridiction="FR",
        regulator_ref="226C0644",
        target_name="FNAC DARTY",
        acquirer_name="GIE FNAC DARTY HOLDING",
        announcement_date=date(2026, 5, 12),
        deal_type="opa",
        status="announced",
        currency="EUR",
    )
    # Legacy synthetic deal (phase-2 noise) — must be deleted
    legacy = Deal(
        juridiction="FR",
        regulator_ref="AMF-SYN-deadbeef1234567890abcdef",
        target_name="[pending parse]",
        acquirer_name="[pending parse]",
        announcement_date=date(2026, 5, 12),
        deal_type="opa",
        status="announced",
        currency="EUR",
    )
    db_session.add_all([legit, legacy])
    await db_session.flush()

    # 2 events attached to the legacy deal — FK CASCADE must drop them
    db_session.add_all(
        [
            Event(
                deal_id=legacy.id,
                ts=datetime.now(tz=UTC),
                event_type="filing_amf",
                description="RSS communiqué",
            ),
            Event(
                deal_id=legacy.id,
                ts=datetime.now(tz=UTC),
                event_type="filing_amf",
                description="another RSS hit",
            ),
        ]
    )
    # 1 event attached to the legit deal — must survive
    db_session.add(
        Event(
            deal_id=legit.id,
            ts=datetime.now(tz=UTC),
            event_type="filing_amf",
            description="BDIF filing",
        )
    )
    await db_session.commit()

    pre_amf_syn = await _count_amf_syn(db_session)
    assert pre_amf_syn == 1

    # Apply the migration's DELETE in-place.
    await db_session.execute(text(_delete_amf_syn_sql()))
    await db_session.commit()

    assert await _count_amf_syn(db_session) == 0
    assert await _count_orphan_events(db_session) == 0

    # Legit deal + its event still there
    remaining = (
        await db_session.execute(
            text("SELECT count(*) FROM deals WHERE regulator_ref = '226C0644'")
        )
    ).scalar_one()
    assert remaining == 1
    legit_events = (
        await db_session.execute(
            text("SELECT count(*) FROM events WHERE description = 'BDIF filing'")
        )
    ).scalar_one()
    assert legit_events == 1


async def test_cleanup_is_idempotent(db_session: AsyncSession) -> None:
    """Re-running the DELETE after first cleanup is harmless."""
    await db_session.execute(text(_delete_amf_syn_sql()))
    await db_session.commit()
    # second time
    await db_session.execute(text(_delete_amf_syn_sql()))
    await db_session.commit()
    assert await _count_amf_syn(db_session) == 0
