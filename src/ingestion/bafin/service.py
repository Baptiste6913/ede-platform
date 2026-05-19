"""BaFin DB service — dedup-aware upsert + `filing_bafin` event emission.

Mirrors the Consob service pattern:
- `(juridiction='DE', regulator_ref=bafin_ref)` is the unique key.
- One `filing_bafin` event per first insertion, carrying the full
  `AngebotsunterlageRecord` payload plus the optional
  `ParsedBafinMetadata` from the PDF body parser.
- Re-running the poller for the same `bafin_ref` is a clean no-op; if
  the PDF was downloaded on a later run, `pdf_path` is back-filled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from src.core.models import Deal, Event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.ingestion.bafin.discovery import AngebotsunterlageRecord
    from src.ingestion.bafin.parser import ParsedBafinMetadata

_log = structlog.get_logger(__name__)

_NAME_MAX_LEN = 255  # Mirrors Deal.target_name / Deal.acquirer_name column width.


def _safe_name(value: str | None) -> str:
    """Truncate to column width and fall back to a sentinel. Phase-4 lesson:
    discovery may still produce odd extractions on weirdly-formatted rows."""
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


async def upsert_deal_from_angebotsunterlage(
    session: AsyncSession,
    record: AngebotsunterlageRecord,
    *,
    pdf_path: Path | None,
    pdf_metadata: ParsedBafinMetadata | None = None,
) -> UpsertResult:
    """Create the `Deal` for a BaFin Angebotsunterlage, or refresh
    `pdf_path` if the row already exists from a previous run."""
    ref = record.bafin_ref
    existing = (
        await session.execute(
            select(Deal).where(Deal.juridiction == "DE").where(Deal.regulator_ref == ref)
        )
    ).scalar_one_or_none()

    if existing is not None:
        if pdf_path is not None and not existing.pdf_path:
            existing.pdf_path = str(pdf_path)
            await session.commit()
        _log.info("bafin.upsert.skipped", ref=ref, deal_id=existing.id)
        return UpsertResult(deal_id=existing.id, created=False)

    offer_price = pdf_metadata.offer_price if pdf_metadata else None
    currency = (pdf_metadata.currency if pdf_metadata else None) or "EUR"
    opening = pdf_metadata.opening_date if pdf_metadata else None
    closing = pdf_metadata.closing_date_est if pdf_metadata else None

    deal = Deal(
        juridiction="DE",
        regulator_ref=ref,
        ticker_target=None,
        target_name=_safe_name(record.target_name),
        acquirer_name=_safe_name(record.bieter_name),
        announcement_date=record.veroeffentlichung_date,
        deal_type=record.deal_type or "opa_volontaire_totalitaria",  # safe default
        status="announced",
        offer_price=offer_price,
        currency=currency,
        expected_close_date=closing,
        source_url=record.wrapper_url,
        pdf_path=str(pdf_path) if pdf_path else None,
    )
    if record.target_isin:
        deal.ticker_target = record.target_isin
    session.add(deal)
    await session.flush()

    session.add(
        Event(
            deal_id=deal.id,
            ts=datetime.now(tz=UTC),
            event_type="filing_bafin",
            description=_describe(record),
            source_url=record.wrapper_url,
            raw_payload=_bafin_event_payload(
                record,
                pdf_metadata=pdf_metadata,
                has_document=pdf_path is not None,
                opening_date=opening,
            ),
        )
    )
    await session.commit()
    _log.info(
        "bafin.upsert.created",
        ref=ref,
        deal_id=deal.id,
        target=record.target_name,
        deal_type=record.deal_type,
        has_document=pdf_path is not None,
    )
    return UpsertResult(deal_id=deal.id, created=True)


def _describe(record: AngebotsunterlageRecord) -> str:
    return (
        f"BaFin Angebotsunterlage — Bieter: {record.bieter_name}, "
        f"Zielgesellschaft: {record.target_name} (ref {record.bafin_ref})"
    )


def _bafin_event_payload(
    record: AngebotsunterlageRecord,
    *,
    pdf_metadata: ParsedBafinMetadata | None,
    has_document: bool,
    opening_date: object,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": "bafin_angebotsunterlagen",
        "has_document": has_document,
        "bafin_ref": record.bafin_ref,
        "target_name": record.target_name,
        "bieter_name": record.bieter_name,
        "target_isin": record.target_isin,
        "offer_type_raw": record.offer_type_raw,
        "deal_type": record.deal_type,
        "veroeffentlichung_date": record.veroeffentlichung_date.isoformat(),
        "wrapper_url": record.wrapper_url,
        "is_amendment": record.is_amendment,
    }
    if pdf_metadata is not None:
        payload["pdf_metadata"] = {
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
            "bieter_name_from_pdf": pdf_metadata.bieter_name_from_pdf,
            "offer_type_from_pdf": pdf_metadata.offer_type_from_pdf,
        }
    if opening_date is not None and hasattr(opening_date, "isoformat"):
        payload["opening_date"] = opening_date.isoformat()
    return payload
