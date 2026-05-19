"""BaFin poller — phase 5 authoritative DE M&A ingestion.

Two entry points:
- `run_backfill(since)`: full sweep of the listing (single monolithic
  page, ~241 rows total, 22-25 within a 12-month window). Used once at
  deploy.
- `run_incremental(since, stop_after_known)`: daily tick that stops
  early as soon as a `bafin_ref` already in DB is seen.

Pipeline: discover → optional PDF download → parse PDF → upsert.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
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
from src.ingestion.bafin import parser as bafin_parser
from src.ingestion.bafin.discovery import (
    LISTING_HEADERS,
    AngebotsunterlageRecord,
    BafinDiscoveryClient,
)
from src.ingestion.bafin.fetcher import BafinPdfFetcher
from src.ingestion.bafin.service import upsert_deal_from_angebotsunterlage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)

_BACKFILL_DAYS_DEFAULT = 365
_INCREMENTAL_DAYS_DEFAULT = 90


@dataclass(frozen=True, slots=True)
class BafinPollResult:
    discovered: int
    created: int
    skipped: int
    pdf_downloaded: int
    pdf_failed: int
    stopped_on_known: bool = False


class BafinPoller:
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        discovery: BafinDiscoveryClient | None = None,
        pdf_fetcher: BafinPdfFetcher | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        settings = get_settings()
        self._session_factory = session_factory or get_sessionmaker()
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.poller_amf_timeout_seconds),
            follow_redirects=True,
            headers=LISTING_HEADERS,
        )
        self._rate_limiter = rate_limiter or RateLimiter(
            settings.poller_amf_rate_per_second,
            jitter_seconds=settings.poller_amf_jitter_seconds,
        )
        self._discovery = discovery or BafinDiscoveryClient(self._http)
        self._pdf_fetcher = pdf_fetcher or BafinPdfFetcher(self._http, self._rate_limiter)

    async def aclose(self) -> None:
        await self._discovery.aclose()
        if self._owns_http:
            await self._http.aclose()

    async def run_backfill(
        self,
        *,
        since: date | None = None,
    ) -> BafinPollResult:
        effective_since = since or (date.today() - timedelta(days=_BACKFILL_DAYS_DEFAULT))
        return await self._run(stop_after_known=False, since=effective_since)

    async def run_incremental(
        self,
        *,
        since: date | None = None,
    ) -> BafinPollResult:
        effective_since = since or (date.today() - timedelta(days=_INCREMENTAL_DAYS_DEFAULT))
        return await self._run(stop_after_known=True, since=effective_since)

    async def _run(
        self,
        *,
        stop_after_known: bool,
        since: date,
    ) -> BafinPollResult:
        discovered = 0
        created = 0
        skipped = 0
        pdf_dl = 0
        pdf_fail = 0
        stopped_on_known = False

        async with self._session_factory() as session:
            async for record in self._discovery.iter_all(since=since):
                discovered += 1
                if stop_after_known and await _ref_already_known(session, record.bafin_ref):
                    stopped_on_known = True
                    _log.info(
                        "bafin.incremental.stop_on_known",
                        ref=record.bafin_ref,
                        discovered=discovered,
                    )
                    break

                pdf_path = await self._download_pdf_safe(record)
                if pdf_path is not None:
                    pdf_dl += 1
                else:
                    pdf_fail += 1

                pdf_md = (
                    bafin_parser.extract_pdf_metadata(pdf_path) if pdf_path is not None else None
                )

                result = await upsert_deal_from_angebotsunterlage(
                    session,
                    record,
                    pdf_path=pdf_path,
                    pdf_metadata=pdf_md,
                )
                if result.created:
                    created += 1
                else:
                    skipped += 1

        _log.info(
            "bafin.poll.run",
            discovered=discovered,
            created=created,
            skipped=skipped,
            pdf_downloaded=pdf_dl,
            pdf_failed=pdf_fail,
            stopped_on_known=stopped_on_known,
        )
        return BafinPollResult(
            discovered=discovered,
            created=created,
            skipped=skipped,
            pdf_downloaded=pdf_dl,
            pdf_failed=pdf_fail,
            stopped_on_known=stopped_on_known,
        )

    async def _download_pdf_safe(self, record: AngebotsunterlageRecord) -> Path | None:
        try:
            return await self._pdf_fetcher.download(
                record.wrapper_url,
                bafin_ref=record.bafin_ref,
                year=record.veroeffentlichung_date.year,
            )
        except Exception as exc:
            _log.warning(
                "bafin.pdf.download_failed",
                ref=record.bafin_ref,
                wrapper=record.wrapper_url,
                error=str(exc),
            )
            return None


async def _ref_already_known(session: AsyncSession, ref: str) -> bool:
    found = await session.execute(
        select(Deal.id).where(Deal.juridiction == "DE").where(Deal.regulator_ref == ref)
    )
    return found.first() is not None


def start_scheduled_bafin_poller(
    scheduler: AsyncIOScheduler,
    *,
    interval_minutes: int = 60,
) -> BafinPoller:
    poller = BafinPoller()

    async def _job() -> None:
        try:
            await poller.run_incremental()
        except Exception:
            _log.exception("bafin.poll.job_crashed")

    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=interval_minutes,
        id="bafin_poller",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return poller
