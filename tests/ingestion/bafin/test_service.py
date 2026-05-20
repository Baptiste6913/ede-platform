"""Tests for src.ingestion.bafin.service — upsert + dedup + event payload."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from src.core.models import Deal, Event
from src.ingestion.bafin.discovery import AngebotsunterlageRecord
from src.ingestion.bafin.parser import ParsedBafinMetadata
from src.ingestion.bafin.service import upsert_deal_from_angebotsunterlage

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _record(**kw: object) -> AngebotsunterlageRecord:
    defaults: dict[str, object] = {
        "bafin_ref": "BAFIN-DE000CBK1001-20260505",
        "bieter_name": "UniCredit S.p.A.",
        "target_name": "COMMERZBANK Aktiengesellschaft",
        "target_isin": "DE000CBK1001",
        "offer_type_raw": "Übernahmeangebot",
        "deal_type": "opa_volontaire_totalitaria",
        "wrapper_url": "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.html?nn=151388",
        "veroeffentlichung_date": date(2026, 5, 5),
        "is_amendment": False,
        "discovered_at": datetime(2026, 5, 19, tzinfo=UTC),
    }
    defaults.update(kw)
    return AngebotsunterlageRecord(**defaults)  # type: ignore[arg-type]


async def test_upsert_creates_de_deal_with_event(db_session: AsyncSession) -> None:
    result = await upsert_deal_from_angebotsunterlage(db_session, _record(), pdf_path=None)
    assert result.created is True
    deal = (
        await db_session.execute(
            select(Deal).where(Deal.regulator_ref == "BAFIN-DE000CBK1001-20260505")
        )
    ).scalar_one()
    assert deal.juridiction == "DE"
    assert deal.target_name == "COMMERZBANK Aktiengesellschaft"
    assert deal.acquirer_name == "UniCredit S.p.A."
    assert deal.deal_type == "opa_volontaire_totalitaria"
    assert deal.announcement_date == date(2026, 5, 5)
    assert deal.ticker_target == "DE000CBK1001"

    events = (
        (await db_session.execute(select(Event).where(Event.deal_id == deal.id))).scalars().all()
    )
    assert len(events) == 1
    e = events[0]
    assert e.event_type == "filing_bafin"
    payload = e.raw_payload or {}
    assert payload["source"] == "bafin_angebotsunterlagen"
    assert payload["bafin_ref"] == "BAFIN-DE000CBK1001-20260505"
    assert payload["target_isin"] == "DE000CBK1001"
    assert payload["is_amendment"] is False


async def test_upsert_idempotent_on_duplicate_ref(db_session: AsyncSession) -> None:
    a = await upsert_deal_from_angebotsunterlage(db_session, _record(), pdf_path=None)
    b = await upsert_deal_from_angebotsunterlage(db_session, _record(), pdf_path=None)
    assert a.created is True
    assert b.created is False
    assert b.deal_id == a.deal_id
    events = (await db_session.execute(select(Event))).scalars().all()
    assert len(events) == 1


async def test_upsert_promotes_pdf_path_on_rerun(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    first = await upsert_deal_from_angebotsunterlage(db_session, _record(), pdf_path=None)
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    await upsert_deal_from_angebotsunterlage(db_session, _record(), pdf_path=pdf)
    deal = (await db_session.execute(select(Deal).where(Deal.id == first.deal_id))).scalar_one()
    assert deal.pdf_path == str(pdf)


async def test_upsert_uses_pdf_metadata_when_provided(
    db_session: AsyncSession,
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    md = ParsedBafinMetadata(
        opening_date=date(2026, 5, 10),
        closing_date_est=date(2026, 6, 12),
        offer_price=Decimal("19.50"),
        currency="EUR",
        target_name_from_pdf=None,
        bieter_name_from_pdf=None,
        offer_type_from_pdf="Übernahmeangebot",
    )
    await upsert_deal_from_angebotsunterlage(db_session, _record(), pdf_path=pdf, pdf_metadata=md)
    deal = (
        await db_session.execute(
            select(Deal).where(Deal.regulator_ref == "BAFIN-DE000CBK1001-20260505")
        )
    ).scalar_one()
    assert deal.offer_price == Decimal("19.50")
    assert deal.currency == "EUR"
    assert deal.expected_close_date == date(2026, 6, 12)
    e = (await db_session.execute(select(Event).where(Event.deal_id == deal.id))).scalar_one()
    payload = e.raw_payload or {}
    assert payload["pdf_metadata"]["offer_price"] == "19.50"
    assert payload["opening_date"] == "2026-05-10"


async def test_upsert_truncates_overlong_names_to_255_chars(
    db_session: AsyncSession,
) -> None:
    record = _record(
        bafin_ref="BAFIN-overlong",
        target_name="Long target " + "x" * 500,
        bieter_name="Long bieter " + "y" * 500,
    )
    result = await upsert_deal_from_angebotsunterlage(db_session, record, pdf_path=None)
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert len(deal.target_name) <= 255
    assert len(deal.acquirer_name) <= 255


async def test_upsert_uses_delisting_offer_enum_value(db_session: AsyncSession) -> None:
    record = _record(
        bafin_ref="BAFIN-DE000DELIST01-20260101",
        offer_type_raw="Delisting-Erwerbsangebot",
        deal_type="delisting_offer",
    )
    result = await upsert_deal_from_angebotsunterlage(db_session, record, pdf_path=None)
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.deal_type == "delisting_offer"
