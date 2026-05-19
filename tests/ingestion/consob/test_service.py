"""Tests for src.ingestion.consob.service — dedup-aware upsert."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from src.core.models import Deal, Event
from src.ingestion.consob.discovery import OpaRecord
from src.ingestion.consob.parser import ParsedConsobMetadata
from src.ingestion.consob.service import upsert_deal_from_opa

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _opa(**kw: object) -> OpaRecord:
    defaults: dict[str, object] = {
        "consob_ref": "CONSOB-opa_bancasistema_20260511",
        "period_start": date(2026, 5, 11),
        "period_end": date(2026, 6, 12),
        "description": "Offerta pubblica di acquisto e scambio obbligatoria",
        "target_name": "Banca Sistema Spa",
        "offerente_name": "Banca CF+ Credito Fondiario Spa",
        "deal_type": "opas",
        "documento_offerta_url": (
            "https://www.consob.it/documents/.../opa_bancasistema_20260511.pdf/u?dl=0"
        ),
        "additional_links": (),
        "page_number": 1,
        "discovered_at": datetime(2026, 5, 19, tzinfo=UTC),
    }
    defaults.update(kw)
    return OpaRecord(**defaults)  # type: ignore[arg-type]


async def test_upsert_creates_it_deal_with_filing_event(db_session: AsyncSession) -> None:
    result = await upsert_deal_from_opa(db_session, _opa(), pdf_path=None)
    assert result.created is True

    deal = (
        await db_session.execute(
            select(Deal).where(Deal.regulator_ref == "CONSOB-opa_bancasistema_20260511")
        )
    ).scalar_one()
    assert deal.juridiction == "IT"
    assert deal.target_name == "Banca Sistema Spa"
    assert deal.acquirer_name == "Banca CF+ Credito Fondiario Spa"
    assert deal.deal_type == "opas"
    assert deal.announcement_date == date(2026, 5, 11)
    assert deal.expected_close_date == date(2026, 6, 12)

    events = (
        (await db_session.execute(select(Event).where(Event.deal_id == deal.id))).scalars().all()
    )
    assert len(events) == 1
    e = events[0]
    assert e.event_type == "filing_consob"
    payload = e.raw_payload or {}
    assert payload["source"] == "consob_documenti_opa"
    assert payload["has_document"] is False
    assert payload["consob_ref"] == "CONSOB-opa_bancasistema_20260511"


async def test_upsert_is_idempotent_on_duplicate_ref(db_session: AsyncSession) -> None:
    first = await upsert_deal_from_opa(db_session, _opa(), pdf_path=None)
    second = await upsert_deal_from_opa(db_session, _opa(), pdf_path=None)
    assert first.created is True
    assert second.created is False
    assert second.deal_id == first.deal_id
    events = (await db_session.execute(select(Event))).scalars().all()
    assert len(events) == 1


async def test_upsert_promotes_pdf_path_on_rerun(db_session: AsyncSession, tmp_path: Path) -> None:
    first = await upsert_deal_from_opa(db_session, _opa(), pdf_path=None)
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    await upsert_deal_from_opa(db_session, _opa(), pdf_path=pdf)
    deal = (await db_session.execute(select(Deal).where(Deal.id == first.deal_id))).scalar_one()
    assert deal.pdf_path == str(pdf)


async def test_upsert_uses_pdf_metadata_when_provided(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    md = ParsedConsobMetadata(
        official_visa="Comunicazione n. 23-456",
        announcement_date=date(2026, 5, 5),
        opening_date=date(2026, 5, 11),
        closing_date_est=date(2026, 6, 12),
        offer_price=Decimal("28.50"),
        currency="EUR",
        target_name_from_pdf=None,
        offerente_name_from_pdf=None,
    )
    await upsert_deal_from_opa(db_session, _opa(), pdf_path=pdf, pdf_metadata=md)
    deal = (
        await db_session.execute(
            select(Deal).where(Deal.regulator_ref == "CONSOB-opa_bancasistema_20260511")
        )
    ).scalar_one()
    # PDF announcement_date takes precedence over listing period_start
    assert deal.announcement_date == date(2026, 5, 5)
    assert deal.offer_price == Decimal("28.50")
    assert deal.currency == "EUR"
    # Event payload carries the pdf_metadata block
    e = (await db_session.execute(select(Event).where(Event.deal_id == deal.id))).scalar_one()
    payload = e.raw_payload or {}
    assert payload["has_document"] is True
    assert payload["pdf_metadata"]["official_visa"] == "Comunicazione n. 23-456"
    assert payload["pdf_metadata"]["offer_price"] == "28.50"


async def test_upsert_unknown_deal_type_falls_back_to_default(
    db_session: AsyncSession,
) -> None:
    record = _opa(consob_ref="CONSOB-x", deal_type=None)
    result = await upsert_deal_from_opa(db_session, record, pdf_path=None)
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.deal_type == "opa_volontaire_totalitaria"  # safe default
