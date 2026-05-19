"""Consob DB service — dedup-aware upsert + `filing_consob` event emission.

Mirrors the BDIF service pattern from phase 3:
- `(juridiction='IT', regulator_ref=consob_ref)` is the unique key.
- One `filing_consob` event per first insertion, carrying the full
  `OpaRecord` payload plus the optional `ParsedConsobMetadata` from the
  PDF body parser.
- Re-running the poller for the same `consob_ref` is a clean no-op; if
  the PDF was downloaded on a later run, `pdf_path` is back-filled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from src.core.models import Deal, Event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.ingestion.consob.discovery import OpaRecord
    from src.ingestion.consob.parser import ParsedConsobMetadata

_log = structlog.get_logger(__name__)

_NAME_MAX_LEN = 255  # Mirrors Deal.target_name / Deal.acquirer_name column width.


def _safe_name(value: str | None) -> str:
    """Truncate to the column width and fall back to a sentinel.

    Defensive: discovery may still produce odd extractions on
    weirdly-formatted rows; this keeps the upsert from crashing the
    whole backfill on a single bad row.
    """
    if not value:
        return "[pending parse]"
    text = value.strip()
    if len(text) > _NAME_MAX_LEN:
        text = text[:_NAME_MAX_LEN].rstrip()
    return text or "[pending parse]"


@dataclass(frozen=True, slots=True)
class UpsertResult:
    deal_id: int
    created: bool


async def upsert_deal_from_opa(
    session: AsyncSession,
    record: OpaRecord,
    *,
    pdf_path: Path | None,
    pdf_metadata: ParsedConsobMetadata | None = None,
) -> UpsertResult:
    """Create the `Deal` for an Italian OPA record, or refresh `pdf_path`
    if the row already exists from a previous run."""
    ref = record.consob_ref
    existing = (
        await session.execute(
            select(Deal).where(Deal.juridiction == "IT").where(Deal.regulator_ref == ref)
        )
    ).scalar_one_or_none()

    if existing is not None:
        if pdf_path is not None and not existing.pdf_path:
            existing.pdf_path = str(pdf_path)
            await session.commit()
        _log.info("consob.upsert.skipped", ref=ref, deal_id=existing.id)
        return UpsertResult(deal_id=existing.id, created=False)

    announcement = (
        (pdf_metadata.announcement_date if pdf_metadata else None)
        or record.period_start
        or date.today()
    )
    offer_price = pdf_metadata.offer_price if pdf_metadata else None
    currency = (pdf_metadata.currency if pdf_metadata else None) or "EUR"

    deal = Deal(
        juridiction="IT",
        regulator_ref=ref,
        target_name=_safe_name(record.target_name),
        acquirer_name=_safe_name(record.offerente_name),
        announcement_date=announcement,
        deal_type=record.deal_type or "opa_volontaire_totalitaria",
        status="announced",
        offer_price=offer_price,
        currency=currency,
        expected_close_date=record.period_end,
        source_url=record.documento_offerta_url,
        pdf_path=str(pdf_path) if pdf_path else None,
    )
    session.add(deal)
    await session.flush()

    session.add(
        Event(
            deal_id=deal.id,
            ts=datetime.now(tz=UTC),
            event_type="filing_consob",
            description=_describe(record),
            source_url=record.documento_offerta_url,
            raw_payload=_consob_event_payload(
                record,
                pdf_metadata=pdf_metadata,
                has_document=pdf_path is not None,
            ),
        )
    )
    await session.commit()
    _log.info(
        "consob.upsert.created",
        ref=ref,
        deal_id=deal.id,
        target=record.target_name,
        deal_type=record.deal_type,
        has_document=pdf_path is not None,
    )
    return UpsertResult(deal_id=deal.id, created=True)


def _describe(record: OpaRecord) -> str:
    target = record.target_name or "?"
    offerente = record.offerente_name or "?"
    return (
        f"Consob documento d'offerta — offerente: {offerente}, "
        f"visée: {target} (ref {record.consob_ref})"
    )


def _consob_event_payload(
    record: OpaRecord,
    *,
    pdf_metadata: ParsedConsobMetadata | None,
    has_document: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": "consob_documenti_opa",
        "has_document": has_document,
        "consob_ref": record.consob_ref,
        "target_name": record.target_name,
        "offerente_name": record.offerente_name,
        "deal_type": record.deal_type,
        "period_start": record.period_start.isoformat() if record.period_start else None,
        "period_end": record.period_end.isoformat() if record.period_end else None,
        "description": record.description,
        "additional_links": [
            {"label": label, "url": url} for label, url in record.additional_links
        ],
        "page_number": record.page_number,
    }
    if pdf_metadata is not None:
        payload["pdf_metadata"] = {
            "official_visa": pdf_metadata.official_visa,
            "announcement_date": pdf_metadata.announcement_date.isoformat()
            if pdf_metadata.announcement_date
            else None,
            "opening_date": pdf_metadata.opening_date.isoformat()
            if pdf_metadata.opening_date
            else None,
            "closing_date_est": pdf_metadata.closing_date_est.isoformat()
            if pdf_metadata.closing_date_est
            else None,
            "offer_price": str(pdf_metadata.offer_price)
            if isinstance(pdf_metadata.offer_price, Decimal)
            else None,
            "currency": pdf_metadata.currency,
            "target_name_from_pdf": pdf_metadata.target_name_from_pdf,
            "offerente_name_from_pdf": pdf_metadata.offerente_name_from_pdf,
        }
    return payload
