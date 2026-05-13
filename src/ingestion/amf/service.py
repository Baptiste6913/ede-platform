"""AMF DB service — dedup, upsert, event emission.

Idempotent insertion: a `Deal` is uniquely identified by
(`juridiction='FR'`, `regulator_ref`). If `regulator_ref` is missing from
the RSS title, we fall back to `sha256(title + published_date)[:32]` so the
unique constraint still holds.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from src.core.models import Deal, Event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.ingestion.amf.parser import ParsedMetadata
    from src.ingestion.amf.rss_watcher import RssItem

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class UpsertResult:
    """Outcome of a single upsert attempt."""

    deal_id: int
    created: bool  # True if a new row was inserted, False if it already existed


def derive_regulator_ref(item: RssItem) -> str:
    """Return `item.regulator_ref` if set, else a deterministic synthetic ref.

    Synthetic refs use the prefix `AMF-SYN-` so they're trivially recognisable
    as fallbacks during downstream review.
    """
    if item.regulator_ref:
        return item.regulator_ref
    seed = item.title + "|" + (item.published_date.isoformat() if item.published_date else "")
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return f"AMF-SYN-{digest}"


async def upsert_deal(
    session: AsyncSession,
    item: RssItem,
    metadata: ParsedMetadata,
    *,
    pdf_path: Path | None,
) -> UpsertResult:
    """Insert a `Deal` if no row with this (juridiction, regulator_ref) exists.

    Also emits a `filing_amf` event on insert (or skips it on duplicate).
    Returns whether the row was newly created.
    """
    ref = derive_regulator_ref(item)
    announcement = metadata.announcement_date or item.published_date or date.today()
    deal_type = metadata.deal_type or "opa"  # safe default; analyst can correct later

    existing = (
        await session.execute(
            select(Deal).where(Deal.juridiction == "FR").where(Deal.regulator_ref == ref)
        )
    ).scalar_one_or_none()

    if existing is not None:
        _log.info("amf.upsert.skipped", ref=ref, deal_id=existing.id)
        return UpsertResult(deal_id=existing.id, created=False)

    deal = Deal(
        juridiction="FR",
        regulator_ref=ref,
        target_name=metadata.target_name or "[pending parse]",
        acquirer_name=metadata.acquirer_name or "[pending parse]",
        announcement_date=announcement,
        deal_type=deal_type,
        status="announced",
        offer_price=metadata.offer_price,
        currency=metadata.currency or "EUR",
        source_url=item.link or None,
        pdf_path=str(pdf_path) if pdf_path else None,
    )
    session.add(deal)
    await session.flush()  # populate deal.id without committing

    session.add(
        Event(
            deal_id=deal.id,
            ts=datetime.now(tz=UTC),
            event_type="filing_amf",
            description=f"Initial AMF filing detected via RSS: {item.title[:200]}",
            source_url=item.link or None,
            raw_payload={
                "rss_title": item.title,
                "rss_published": item.published.isoformat() if item.published else None,
                "regulator_ref_raw": item.regulator_ref,
                "regulator_ref_used": ref,
                "metadata": {
                    "target_name": metadata.target_name,
                    "acquirer_name": metadata.acquirer_name,
                    "deal_type": metadata.deal_type,
                    "offer_price": str(metadata.offer_price)
                    if isinstance(metadata.offer_price, Decimal)
                    else None,
                    "currency": metadata.currency,
                },
            },
        )
    )
    await session.commit()
    _log.info(
        "amf.upsert.created",
        ref=ref,
        deal_id=deal.id,
        title=item.title[:120],
    )
    return UpsertResult(deal_id=deal.id, created=True)
