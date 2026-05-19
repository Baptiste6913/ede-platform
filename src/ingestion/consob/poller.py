"""Consob poller — phase 4 authoritative IT M&A ingestion.

Two entry points:
- `run_backfill(max_pages)`: full sweep of the listing, used once at
  deploy to populate ~12 months of OPAs.
- `run_incremental(stop_after_known)`: daily tick that stops early as
  soon as a `consob_ref` already in DB is seen — keeps the ScrapingBee
  credit budget tight (typically 1 listing page + a few PDFs per day).

Both paths share the same orchestration:
    discover → atomic PDF download (httpx, 0 credits) → parse PDF → upsert
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from src.core.db import get_sessionmaker
from src.core.models import Deal
from src.core.settings import get_settings
from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.consob import parser as consob_parser
from src.ingestion.consob.discovery import ConsobDiscoveryClient, OpaRecord
from src.ingestion.consob.fetcher import ConsobPdfFetcher
from src.ingestion.consob.scrapingbee_client import (
    ScrapingBeeBudgetExceeded,
    ScrapingBeeClient,
)
from src.ingestion.consob.service import upsert_deal_from_opa

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ConsobPollResult:
    discovered: int
    created: int
    skipped: int
    pdf_downloaded: int
    pdf_failed: int
    credits_consumed: int
    stopped_on_known: bool = False
    budget_exhausted: bool = False


class ConsobPoller:
    def __init__(
        self,
        *,
        scrapingbee: ScrapingBeeClient | None = None,
        pdf_client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        discovery: ConsobDiscoveryClient | None = None,
        pdf_fetcher: ConsobPdfFetcher | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        settings = get_settings()
        self._session_factory = session_factory or get_sessionmaker()
        self._scrapingbee = scrapingbee or ScrapingBeeClient(self._session_factory)
        self._owns_pdf_client = pdf_client is None
        self._pdf_client = pdf_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.poller_amf_timeout_seconds),
            follow_redirects=True,
        )
        self._rate_limiter = rate_limiter or RateLimiter(
            settings.poller_amf_rate_per_second,
            jitter_seconds=settings.poller_amf_jitter_seconds,
        )
        self._discovery = discovery or ConsobDiscoveryClient(self._scrapingbee)
        self._pdf_fetcher = pdf_fetcher or ConsobPdfFetcher(self._pdf_client, self._rate_limiter)

    async def aclose(self) -> None:
        await self._scrapingbee.aclose()
        if self._owns_pdf_client:
            await self._pdf_client.aclose()

    async def run_backfill(self, *, max_pages: int | None = None) -> ConsobPollResult:
        return await self._run(stop_after_known=False, max_pages=max_pages)

    async def run_incremental(self, *, max_pages: int = 2) -> ConsobPollResult:
        return await self._run(stop_after_known=True, max_pages=max_pages)

    async def _run(
        self,
        *,
        stop_after_known: bool,
        max_pages: int | None,
    ) -> ConsobPollResult:
        discovered = 0
        created = 0
        skipped = 0
        pdf_dl = 0
        pdf_fail = 0
        credits_start = await self._scrapingbee.used_credits_this_month()
        stopped_on_known = False
        budget_exhausted = False

        try:
            async with self._session_factory() as session:
                async for record in self._discovery.iter_all(max_pages=max_pages):
                    discovered += 1
                    if stop_after_known and await _ref_already_known(session, record.consob_ref):
                        stopped_on_known = True
                        _log.info(
                            "consob.incremental.stop_on_known",
                            ref=record.consob_ref,
                            discovered=discovered,
                        )
                        break

                    pdf_path = await self._download_pdf_safe(record)
                    if pdf_path is not None:
                        pdf_dl += 1
                    elif record.documento_offerta_url is not None:
                        pdf_fail += 1

                    pdf_md = (
                        consob_parser.extract_pdf_metadata(pdf_path)
                        if pdf_path is not None
                        else None
                    )

                    result = await upsert_deal_from_opa(
                        session,
                        record,
                        pdf_path=pdf_path,
                        pdf_metadata=pdf_md,
                    )
                    if result.created:
                        created += 1
                    else:
                        skipped += 1
        except ScrapingBeeBudgetExceeded as exc:
            _log.error(
                "consob.poll.budget_exhausted",
                used=exc.used,
                budget=exc.budget,
                discovered=discovered,
            )
            budget_exhausted = True

        credits_consumed = await self._scrapingbee.used_credits_this_month() - credits_start

        _log.info(
            "consob.poll.run",
            discovered=discovered,
            created=created,
            skipped=skipped,
            pdf_downloaded=pdf_dl,
            pdf_failed=pdf_fail,
            credits_consumed=credits_consumed,
            stopped_on_known=stopped_on_known,
            budget_exhausted=budget_exhausted,
        )
        return ConsobPollResult(
            discovered=discovered,
            created=created,
            skipped=skipped,
            pdf_downloaded=pdf_dl,
            pdf_failed=pdf_fail,
            credits_consumed=credits_consumed,
            stopped_on_known=stopped_on_known,
            budget_exhausted=budget_exhausted,
        )

    async def _download_pdf_safe(self, record: OpaRecord) -> Path | None:
        url = record.documento_offerta_url
        if url is None:
            return None
        year = record.period_start.year if record.period_start else datetime.now().astimezone().year
        try:
            return await self._pdf_fetcher.download(url, consob_ref=record.consob_ref, year=year)
        except Exception as exc:
            _log.warning(
                "consob.pdf.download_failed",
                ref=record.consob_ref,
                url=url,
                error=str(exc),
            )
            return None


async def _ref_already_known(session: AsyncSession, ref: str) -> bool:
    found = await session.execute(
        select(Deal.id).where(Deal.juridiction == "IT").where(Deal.regulator_ref == ref)
    )
    return found.first() is not None


def start_scheduled_consob_poller(
    scheduler: AsyncIOScheduler,
    *,
    interval_minutes: int = 60,
) -> ConsobPoller:
    poller = ConsobPoller()

    async def _job() -> None:
        try:
            await poller.run_incremental()
        except Exception:
            _log.exception("consob.poll.job_crashed")

    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=interval_minutes,
        id="consob_poller",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return poller
