"""AMF RSS poller — signal-only since phase 3.

`AmfPoller.run_once()` polls the AMF "Communiqués" RSS feed (display/23) and
emits `filing_amf` events on any deal whose canonical `regulator_ref` is
mentioned in the RSS title/summary. Unmatched items are dropped — the RSS
feed contains too much non-M&A noise to safely create deals from it (see
phase-2 live backfill in `artifacts/phase-02/live-backfill.txt`).

Authoritative document ingestion happens in `BdifPoller` (`bdif_poller.py`).

`start_scheduled_poller()` wires this RSS watcher into APScheduler with the
configured interval (default 15 min).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.db import get_sessionmaker
from src.core.settings import get_settings
from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.amf.rss_watcher import RssWatcher
from src.ingestion.amf.service import record_rss_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PollResult:
    """Aggregate outcome of one RSS `run_once()` invocation."""

    matched: int  # items matching the M&A regex
    events_emitted: int  # new filing_amf events
    duplicates: int  # repeat hits on the same RSS link
    unmatched: int  # canonical ref had no matching deal
    no_ref: int  # RSS item had no canonical AMF-YYYY-X-NNNN reference


class AmfPoller:
    """RSS-driven event emitter. Construct once, call `run_once()` per tick."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        rss_watcher: RssWatcher | None = None,
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
        self._session_factory = session_factory or get_sessionmaker()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def run_once(self) -> PollResult:
        items = await self._rss_watcher.fetch()
        matched = len(items)
        emitted = 0
        duplicates = 0
        unmatched = 0
        no_ref = 0

        async with self._session_factory() as session:
            for item in items:
                result = await record_rss_event(session, item)
                if result.emitted:
                    emitted += 1
                elif result.reason == "duplicate":
                    duplicates += 1
                elif result.reason == "no_ref":
                    no_ref += 1
                else:
                    unmatched += 1

        _log.info(
            "amf.rss.poll.run_once",
            matched=matched,
            events_emitted=emitted,
            duplicates=duplicates,
            unmatched=unmatched,
            no_ref=no_ref,
        )
        return PollResult(
            matched=matched,
            events_emitted=emitted,
            duplicates=duplicates,
            unmatched=unmatched,
            no_ref=no_ref,
        )


def start_scheduled_poller(
    scheduler: AsyncIOScheduler,
    *,
    interval_minutes: int | None = None,
) -> AmfPoller:
    """Register the RSS event-only poller on the given APScheduler instance."""
    settings = get_settings()
    interval = (
        interval_minutes if interval_minutes is not None else settings.poller_amf_interval_minutes
    )
    poller = AmfPoller()

    async def _job() -> None:
        try:
            await poller.run_once()
        except Exception:
            _log.exception("amf.rss.poll.job_crashed")

    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=interval,
        id="amf_rss_poller",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return poller
