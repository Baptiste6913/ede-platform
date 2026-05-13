"""AMF poller — top-level orchestration.

`AmfPoller.run_once()` is the unit of work:
    1. fetch RSS
    2. for each matched item:
       a. discover BDIF URL from AMF detail page (best-effort)
       b. download PDF (atomic) — best-effort
       c. parse title + first 5 PDF pages
       d. dedup-aware upsert in `deals` + emit `filing_amf` event

`start_scheduled_poller()` wires the poller into APScheduler with the
configured interval (default 15 min).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.db import get_sessionmaker
from src.core.settings import get_settings
from src.ingestion.amf import parser as amf_parser
from src.ingestion.amf.bdif_fetcher import BdifFetcher, BdifLink
from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.amf.rss_watcher import RssItem, RssWatcher
from src.ingestion.amf.service import upsert_deal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PollResult:
    """Aggregate outcome of one `run_once()` invocation."""

    matched: int
    created: int
    skipped: int
    pdf_downloaded: int
    pdf_failed: int


class AmfPoller:
    """End-to-end orchestrator. Construct once, call `run_once()` per tick."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        rss_watcher: RssWatcher | None = None,
        bdif_fetcher: BdifFetcher | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        settings = get_settings()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.poller_amf_timeout_seconds),
            headers={
                "User-Agent": settings.user_agent,
                "Accept-Language": settings.poller_amf_accept_language,
            },
            follow_redirects=True,
        )
        self._rate_limiter = rate_limiter or RateLimiter(
            settings.poller_amf_rate_per_second,
            jitter_seconds=settings.poller_amf_jitter_seconds,
        )
        self._rss_watcher = rss_watcher or RssWatcher(self._client, self._rate_limiter)
        self._bdif_fetcher = bdif_fetcher or BdifFetcher(self._client, self._rate_limiter)
        self._session_factory = session_factory or get_sessionmaker()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def run_once(self) -> PollResult:
        items = await self._rss_watcher.fetch()
        matched = len(items)
        created = 0
        skipped = 0
        pdf_dl = 0
        pdf_fail = 0

        async with self._session_factory() as session:
            for item in items:
                pdf_path, link = await self._fetch_pdf_safe(item)
                if pdf_path is not None:
                    pdf_dl += 1
                elif link is not None:
                    pdf_fail += 1

                metadata = self._build_metadata(item, pdf_path)
                result = await upsert_deal(session, item, metadata, pdf_path=pdf_path)
                if result.created:
                    created += 1
                else:
                    skipped += 1

        _log.info(
            "amf.poll.run_once",
            matched=matched,
            created=created,
            skipped=skipped,
            pdf_downloaded=pdf_dl,
            pdf_failed=pdf_fail,
        )
        return PollResult(
            matched=matched,
            created=created,
            skipped=skipped,
            pdf_downloaded=pdf_dl,
            pdf_failed=pdf_fail,
        )

    async def _fetch_pdf_safe(
        self,
        item: RssItem,
    ) -> tuple[Path | None, BdifLink | None]:
        """Discover + download the BDIF PDF, swallowing per-item failures.

        Returns `(path, link)` where either or both may be None.
        """
        if not item.link:
            return (None, None)
        try:
            link = await self._bdif_fetcher.discover_bdif_url(item.link)
        except Exception as exc:
            _log.warning("amf.bdif.discover_failed", link=item.link, error=str(exc))
            return (None, None)
        if link is None:
            return (None, None)
        try:
            year = item.published_date.year if item.published_date else link.year
            path = await self._bdif_fetcher.download(link, year=year)
            return (path, link)
        except Exception as exc:
            _log.warning(
                "amf.bdif.download_failed",
                ref=link.regulator_ref,
                error=str(exc),
            )
            return (None, link)

    @staticmethod
    def _build_metadata(
        item: RssItem,
        pdf_path: Path | None,
    ) -> amf_parser.ParsedMetadata:
        title_md = amf_parser.parse_title(item.title)
        if pdf_path is None:
            return title_md
        pdf_md = amf_parser.extract_pdf_metadata(pdf_path)
        return amf_parser.merge(title_md, pdf_md)


def start_scheduled_poller(
    scheduler: AsyncIOScheduler,
    *,
    interval_minutes: int | None = None,
) -> AmfPoller:
    """Register an AMF poller job on the given APScheduler instance.

    The caller is responsible for `scheduler.start()` and the lifecycle of
    the returned `AmfPoller` (call `await poller.aclose()` on shutdown).
    """
    settings = get_settings()
    interval = (
        interval_minutes if interval_minutes is not None else settings.poller_amf_interval_minutes
    )
    poller = AmfPoller()

    async def _job() -> None:
        try:
            await poller.run_once()
        except Exception:
            _log.exception("amf.poll.job_crashed")

    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=interval,
        id="amf_poller",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return poller
