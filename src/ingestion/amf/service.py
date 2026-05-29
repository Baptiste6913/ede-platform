"""AMF DB service — dedup, upsert, event emission.

Two entry points after phase 3 routing change:

- `upsert_deal_from_bdif()` — **authoritative**. BDIF documents create
  full `Deal` rows with real `regulator_ref` (the BDIF `numero`) and a
  `filing_amf` event carrying the document metadata.

- `record_rss_event()` — **signal-only**. An RSS communiqué emits a
  `filing_amf` event ONLY when its embedded canonical reference matches an
  existing BDIF-sourced deal. Unmatched items are logged + dropped (no
  synthetic-ref deals anymore — that was the phase-2 noise source).

Dedup key remains `(juridiction='FR', regulator_ref)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import structlog
from sqlalchemy import select

from src.core.models import Deal, Event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.ingestion.amf.bdif_api import BdifItem
    from src.ingestion.amf.parser import ParsedMetadata
    from src.ingestion.amf.rss_watcher import RssItem

_log = structlog.get_logger(__name__)

# Phase 9.2 02a — AMF-specific offer-price bound.
# Lower 0.01: matches Consob (sub-unit prices like SOCIETE DE TAYNINH 0,11 €
# stay verified). Upper 100_000: accommodates retraits on radiated small-caps
# (LV GROUP 222C0375 at 10 000 € / share, Finexsi-validated) while still
# rejecting OCEANE controvalore artefacts (101 382 €, NBSP-bug class). The
# 80-deal audit sample shows 0 legitimate deals above this ceiling.
PRICE_LOWER_AMF = Decimal("0.01")
PRICE_UPPER_AMF = Decimal("100000")

# Parser revision stamped on every deal whose offer_price is set by this
# pipeline. Mirrors the BaFin PARSER_VERSION pattern (P9.1a) — bump on every
# parser change so backfills can target stale rows.
PARSER_VERSION_02A = 2


@dataclass(frozen=True, slots=True)
class UpsertResult:
    """Outcome of a BDIF deal upsert."""

    deal_id: int
    created: bool


@dataclass(frozen=True, slots=True)
class EventResult:
    """Outcome of an RSS-driven event record."""

    deal_id: int | None
    emitted: bool
    reason: Literal["created", "duplicate", "unmatched", "no_ref"] = "unmatched"


def _derive_quality_flag(md: ParsedMetadata | None) -> str:
    """Map a parsed metadata to the canonical offer_price_quality_flag.

    P9.2 02a (Option A — helper lives in the service, parser untouched):

    - ``md.offer_price is None`` → ``suspect_low_unverified`` (parser silent;
      the default flag, same value as the migration-0015 server default so
      backfills can detect "never re-parsed" rows).
    - ``md.offer_price`` outside the AMF bound → ``failed_validation`` (the
      extraction caught an OCEANE controvalore, a dividend, or a similar
      artefact — the value is real but does not represent the offer price).
    - ``md.offer_price`` inside the bound → ``verified_cash``.
    """
    if md is None or md.offer_price is None:
        return "suspect_low_unverified"
    if md.offer_price < PRICE_LOWER_AMF or md.offer_price > PRICE_UPPER_AMF:
        return "failed_validation"
    return "verified_cash"


async def upsert_deal_from_bdif(
    session: AsyncSession,
    bdif_item: BdifItem,
    *,
    pdf_path: Path | None,
    pdf_metadata: ParsedMetadata | None = None,
) -> UpsertResult:
    """Create or refresh the `Deal` corresponding to a BDIF item.

    P9.2 02a wiring:

    - **New deals** populate ``offer_price``, ``currency``,
      ``offer_price_quality_flag`` (via :func:`_derive_quality_flag`) and
      ``parser_version`` from ``pdf_metadata`` when available.
    - **Existing deals** are back-filled **only** when their current
      ``offer_price_quality_flag`` is still ``suspect_low_unverified`` (the
      migration-0015 default — meaning "never re-parsed"). Already-promoted
      flags (``verified_cash``, ``failed_validation``, etc.) are never
      overwritten — idempotence guard. ``pdf_path`` continues to be promoted
      independently when it was missing.
    """
    if not bdif_item.numero:
        raise ValueError("BdifItem.numero is required (canonical regulator_ref)")

    ref = bdif_item.numero
    existing = (
        await session.execute(
            select(Deal).where(Deal.juridiction == "FR").where(Deal.regulator_ref == ref)
        )
    ).scalar_one_or_none()

    if existing is not None:
        mutated = False
        # Promote pdf_path if we just downloaded the PDF for an existing
        # rss-only event-shell or a previous BDIF run that failed mid-way.
        if pdf_path is not None and not existing.pdf_path:
            existing.pdf_path = str(pdf_path)
            mutated = True
        # Idempotent back-fill: only touch rows still at the default flag so
        # a re-run never overwrites a previously-promoted price (verified_cash,
        # failed_validation, etc.).
        if (
            pdf_metadata is not None
            and existing.offer_price_quality_flag == "suspect_low_unverified"
        ):
            existing.offer_price = pdf_metadata.offer_price
            existing.currency = pdf_metadata.currency or existing.currency or "EUR"
            existing.offer_price_quality_flag = _derive_quality_flag(pdf_metadata)
            existing.parser_version = PARSER_VERSION_02A
            mutated = True
        if mutated:
            await session.commit()
        _log.info("amf.bdif.upsert.skipped", ref=ref, deal_id=existing.id)
        return UpsertResult(deal_id=existing.id, created=False)

    offer_price = pdf_metadata.offer_price if pdf_metadata is not None else None
    currency = (pdf_metadata.currency if pdf_metadata is not None else None) or "EUR"
    quality_flag = _derive_quality_flag(pdf_metadata)

    deal = Deal(
        juridiction="FR",
        regulator_ref=ref,
        target_name=bdif_item.target_name or "[pending parse]",
        acquirer_name=bdif_item.acquirer_name or "[pending parse]",
        announcement_date=bdif_item.announcement_date or date.today(),
        deal_type=bdif_item.deal_type or "opa",
        status="announced",
        offer_price=offer_price,
        currency=currency,
        offer_price_quality_flag=quality_flag,
        parser_version=PARSER_VERSION_02A,
        source_url=_make_bdif_source_url(bdif_item),
        pdf_path=str(pdf_path) if pdf_path else None,
    )
    session.add(deal)
    await session.flush()

    session.add(
        Event(
            deal_id=deal.id,
            ts=datetime.now(tz=UTC),
            event_type="filing_amf",
            description=_describe_bdif(bdif_item),
            source_url=_make_bdif_source_url(bdif_item),
            raw_payload=_bdif_event_payload(bdif_item, has_document=pdf_path is not None),
        )
    )
    await session.commit()
    _log.info(
        "amf.bdif.upsert.created",
        ref=ref,
        deal_id=deal.id,
        target=bdif_item.target_name,
        deal_type=bdif_item.deal_type,
        has_document=pdf_path is not None,
    )
    return UpsertResult(deal_id=deal.id, created=True)


async def record_rss_event(session: AsyncSession, rss_item: RssItem) -> EventResult:
    """Emit a `filing_amf` event when the RSS item references a known deal.

    No deal is created — the RSS feed (display/23, communiqués AMF) is signal-
    only since phase 3. Unmatched items are logged at INFO level and dropped.
    """
    ref = rss_item.regulator_ref
    if not ref:
        _log.info("amf.rss.skipped.no_ref", title=rss_item.title[:120])
        return EventResult(deal_id=None, emitted=False, reason="no_ref")

    deal = (
        await session.execute(
            select(Deal).where(Deal.juridiction == "FR").where(Deal.regulator_ref == ref)
        )
    ).scalar_one_or_none()
    if deal is None:
        _log.info("amf.rss.skipped.unmatched", ref=ref, title=rss_item.title[:120])
        return EventResult(deal_id=None, emitted=False, reason="unmatched")

    # Dedup events on (deal_id, source_url) — re-running the poller must not
    # emit the same event twice.
    src = rss_item.link or None
    if src is not None:
        already = (
            await session.execute(
                select(Event)
                .where(Event.deal_id == deal.id)
                .where(Event.event_type == "filing_amf")
                .where(Event.source_url == src)
            )
        ).first()
        if already is not None:
            _log.info("amf.rss.event.duplicate", ref=ref, deal_id=deal.id)
            return EventResult(deal_id=deal.id, emitted=False, reason="duplicate")

    session.add(
        Event(
            deal_id=deal.id,
            ts=datetime.now(tz=UTC),
            event_type="filing_amf",
            description=f"AMF communiqué (RSS display/23): {rss_item.title[:200]}",
            source_url=src,
            raw_payload={
                "source": "rss_display_23",
                "has_document": False,
                "rss_title": rss_item.title,
                "rss_published": rss_item.published.isoformat() if rss_item.published else None,
                "regulator_ref_matched": ref,
            },
        )
    )
    await session.commit()
    _log.info("amf.rss.event.created", ref=ref, deal_id=deal.id)
    return EventResult(deal_id=deal.id, emitted=True, reason="created")


# --------------------------------------------------------------------- helpers


def _make_bdif_source_url(bdif_item: BdifItem) -> str | None:
    pdf = bdif_item.first_pdf
    return pdf.absolute_url if pdf else None


def _describe_bdif(bdif_item: BdifItem) -> str:
    op = bdif_item.primary_operation or "?"
    target = bdif_item.target_name or "?"
    return f"BDIF note d'information {op} — visée: {target} (numero {bdif_item.numero})"


def _bdif_event_payload(bdif_item: BdifItem, *, has_document: bool) -> dict[str, Any]:
    return {
        "source": "bdif",
        "has_document": has_document,
        "numero": bdif_item.numero,
        "domaine": bdif_item.domaine,
        "types_information": list(bdif_item.types_information),
        "types_document": list(bdif_item.types_document),
        "types_operation": list(bdif_item.types_operation),
        "date_information": (
            bdif_item.date_information.isoformat() if bdif_item.date_information else None
        ),
        "date_publication": (
            bdif_item.date_publication.isoformat() if bdif_item.date_publication else None
        ),
        "societes": [
            {"role": s.role, "raison_sociale": s.raison_sociale, "jeton": s.jeton}
            for s in bdif_item.societes
        ],
        "documents": [
            {"path": d.path, "nom_fichier": d.nom_fichier, "accessible": d.accessible}
            for d in bdif_item.documents
        ],
    }


# kept for backwards compat with tests/callers expecting Decimal handling — no
# longer used since BDIF doesn't expose price in the API; price is extracted
# from the PDF by the analyst/parser layer later (phase 6).
__all__ = [
    "PARSER_VERSION_02A",
    "PRICE_LOWER_AMF",
    "PRICE_UPPER_AMF",
    "Decimal",
    "EventResult",
    "UpsertResult",
    "record_rss_event",
    "upsert_deal_from_bdif",
]
