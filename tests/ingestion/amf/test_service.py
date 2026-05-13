"""Tests for src.ingestion.amf.service (DB upsert + dedup)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from src.core.models import Deal, Event
from src.ingestion.amf.parser import ParsedMetadata
from src.ingestion.amf.rss_watcher import RssItem
from src.ingestion.amf.service import derive_regulator_ref, upsert_deal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _rss(
    title: str = "OPA visant les actions de Algol SA - AMF-2025-D-0421",
    ref: str | None = "AMF-2025-D-0421",
    link: str = "https://www.amf-france.org/fr/details/AMF-2025-D-0421",
) -> RssItem:
    return RssItem(
        title=title,
        link=link,
        summary="",
        published=datetime(2025, 5, 12, 9, 0, tzinfo=UTC),
        regulator_ref=ref,
    )


def _metadata(**kw: object) -> ParsedMetadata:
    base = {
        "deal_type": "opa",
        "target_name": "Algol SA",
        "acquirer_name": "Bidder Holding France",
        "announcement_date": date(2025, 5, 12),
        "offer_price": Decimal("28.50"),
        "currency": "EUR",
    }
    base.update(kw)
    return ParsedMetadata(**base)  # type: ignore[arg-type]


def test_derive_regulator_ref_uses_real_ref() -> None:
    item = _rss(ref="AMF-2025-D-0421")
    assert derive_regulator_ref(item) == "AMF-2025-D-0421"


def test_derive_regulator_ref_falls_back_to_hash_when_missing() -> None:
    item = _rss(ref=None)
    out = derive_regulator_ref(item)
    assert out.startswith("AMF-SYN-")
    assert len(out) == 8 + 24  # 'AMF-SYN-' + 24 hex chars
    # Deterministic: same input → same output
    assert derive_regulator_ref(item) == out


async def test_upsert_creates_deal_and_filing_event(db_session: AsyncSession) -> None:
    result = await upsert_deal(db_session, _rss(), _metadata(), pdf_path=None)
    assert result.created is True

    deal = (
        await db_session.execute(select(Deal).where(Deal.regulator_ref == "AMF-2025-D-0421"))
    ).scalar_one()
    assert deal.juridiction == "FR"
    assert deal.deal_type == "opa"
    assert deal.target_name == "Algol SA"
    assert deal.acquirer_name == "Bidder Holding France"
    assert deal.offer_price == Decimal("28.50")

    events = (
        (await db_session.execute(select(Event).where(Event.deal_id == deal.id))).scalars().all()
    )
    assert len(events) == 1
    assert events[0].event_type == "filing_amf"
    payload = events[0].raw_payload or {}
    assert payload["regulator_ref_used"] == "AMF-2025-D-0421"


async def test_upsert_is_idempotent_on_duplicate_ref(db_session: AsyncSession) -> None:
    first = await upsert_deal(db_session, _rss(), _metadata(), pdf_path=None)
    assert first.created is True

    second = await upsert_deal(db_session, _rss(), _metadata(), pdf_path=None)
    assert second.created is False
    assert second.deal_id == first.deal_id

    # Only one event emitted across both upserts.
    events = (
        (await db_session.execute(select(Event).where(Event.deal_id == first.deal_id)))
        .scalars()
        .all()
    )
    assert len(events) == 1


async def test_upsert_uses_synthetic_ref_when_rss_has_none(
    db_session: AsyncSession,
) -> None:
    item = _rss(ref=None, title="OPA mystérieuse", link="")
    result = await upsert_deal(db_session, item, _metadata(), pdf_path=None)
    assert result.created is True

    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.regulator_ref.startswith("AMF-SYN-")


async def test_upsert_persists_pdf_path(db_session: AsyncSession, tmp_path: object) -> None:
    from pathlib import Path

    pdf = Path(str(tmp_path)) / "note.pdf"
    pdf.write_bytes(b"%PDF-1.4 (stub)")
    result = await upsert_deal(db_session, _rss(), _metadata(), pdf_path=pdf)
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.pdf_path == str(pdf)
