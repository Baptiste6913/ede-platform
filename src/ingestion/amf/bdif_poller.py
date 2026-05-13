"""BDIF poller — authoritative AMF M&A document ingestion (phase 3).

For each item returned by the BDIF search API:
    1. derive the year of the document (date_information or date_publication)
    2. atomically download the PDF to ${DATA_DIR}/pdfs/fr/{year}/{numero}.pdf
    3. upsert a `Deal` row keyed on (juridiction='FR', regulator_ref=numero)
    4. emit a `filing_amf` event with the full BDIF payload (`has_document=True`)

Unlike the RSS poller, this is the canonical pipeline: it always carries the
document and the real BDIF reference, so dedup is reliable and no synthetic
`AMF-SYN-*` refs are ever produced.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.db import get_sessionmaker
from src.core.settings import get_settings
from src.ingestion.amf.bdif_api import BdifApiClient, BdifItem
from src.ingestion.amf.rate_limiter import RateLimiter, retry_with_backoff
from src.ingestion.amf.service import upsert_deal_from_bdif

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)

# Min size for a real BDIF PDF (anything smaller is almost certainly an
# error page or interstitial).
_MIN_PDF_BYTES = 1024


@dataclass(frozen=True, slots=True)
class BdifPollResult:
    """Aggregate outcome of one `BdifPoller.run_once()`."""

    discovered: int  # items the API returned that matched our filters
    created: int  # new Deal rows inserted
    skipped: int  # Deal already existed (dedup)
    pdf_downloaded: int
    pdf_failed: int


class BdifPoller:
    """End-to-end authoritative ingestion of AMF BDIF notes d'information."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limiter: RateLimiter | None = None,
        api: BdifApiClient | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        data_dir: str | None = None,
        max_items: int | None = None,
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
        self._api = api or BdifApiClient(self._client, self._rate_limiter)
        self._session_factory = session_factory or get_sessionmaker()
        self._data_dir = Path(data_dir or settings.data_dir)
        self._max_items = max_items
        self._max_retries = settings.poller_amf_max_retries

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def run_once(self) -> BdifPollResult:
        discovered = 0
        created = 0
        skipped = 0
        pdf_dl = 0
        pdf_fail = 0

        async with self._session_factory() as session:
            async for item in self._api.iter_all(
                types_information=("OPA",),
                types_document=("NotesEtAutresInformations",),
                max_items=self._max_items,
            ):
                discovered += 1
                pdf_path = await self._download_safe(item)
                if pdf_path is not None:
                    pdf_dl += 1
                elif item.first_pdf is not None:
                    pdf_fail += 1

                result = await upsert_deal_from_bdif(session, item, pdf_path=pdf_path)
                if result.created:
                    created += 1
                else:
                    skipped += 1

        _log.info(
            "amf.bdif.poll.run_once",
            discovered=discovered,
            created=created,
            skipped=skipped,
            pdf_downloaded=pdf_dl,
            pdf_failed=pdf_fail,
        )
        return BdifPollResult(
            discovered=discovered,
            created=created,
            skipped=skipped,
            pdf_downloaded=pdf_dl,
            pdf_failed=pdf_fail,
        )

    async def _download_safe(self, item: BdifItem) -> Path | None:
        """Download the first accessible PDF for `item`, atomically. Swallow
        per-item failures (logged + counted)."""
        pdf = item.first_pdf
        if pdf is None:
            return None
        year = _year_for_item(item)
        target_dir = self._data_dir / "pdfs" / "fr" / str(year)
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / f"{item.numero}.pdf"
        if final_path.exists() and final_path.stat().st_size > 0:
            _log.info("amf.bdif.pdf.cached", numero=item.numero, path=str(final_path))
            return final_path

        await self._rate_limiter.acquire()
        try:
            content = await retry_with_backoff(
                lambda: self._fetch_pdf_bytes(pdf.absolute_url),
                max_retries=self._max_retries,
                service="amf-bdif-pdf",
            )
        except Exception as exc:
            _log.warning(
                "amf.bdif.pdf.download_failed",
                numero=item.numero,
                url=pdf.absolute_url,
                error=str(exc),
            )
            return None

        # Atomic write via mkstemp + os.replace.
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{item.numero}.",
            suffix=".pdf.part",
            dir=str(target_dir),
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            os.replace(tmp_name, final_path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

        _log.info(
            "amf.bdif.pdf.downloaded",
            numero=item.numero,
            bytes=len(content),
            path=str(final_path),
        )
        return final_path

    async def _fetch_pdf_bytes(self, url: str) -> bytes:
        resp = await self._client.get(
            url,
            headers={
                "Accept": "application/pdf,application/octet-stream,*/*",
                "Referer": "https://bdif.amf-france.org/fr",
            },
        )
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "").lower()
        if "pdf" not in ctype and len(resp.content) < _MIN_PDF_BYTES:
            from src.core.exceptions import ExternalServiceError

            raise ExternalServiceError(
                "amf-bdif-pdf",
                f"unexpected content-type {ctype!r} / short response ({len(resp.content)}b)",
            )
        return resp.content


def _year_for_item(item: BdifItem) -> int:
    """Year used in the storage path. Prefers dateInformation, falls back
    to datePublication, then current year."""
    if item.date_information:
        return item.date_information.year
    if item.date_publication:
        return item.date_publication.year
    return datetime.now().astimezone().year


def start_scheduled_bdif_poller(
    scheduler: AsyncIOScheduler,
    *,
    interval_minutes: int | None = None,
    max_items: int | None = 50,
) -> BdifPoller:
    """Register the BDIF poller on the given APScheduler instance."""
    settings = get_settings()
    interval = (
        interval_minutes if interval_minutes is not None else settings.poller_amf_interval_minutes
    )
    poller = BdifPoller(max_items=max_items)

    async def _job() -> None:
        try:
            await poller.run_once()
        except Exception:
            _log.exception("amf.bdif.poll.job_crashed")

    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=interval,
        id="amf_bdif_poller",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return poller
