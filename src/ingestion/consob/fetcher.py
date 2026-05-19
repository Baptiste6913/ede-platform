"""Consob PDF fetcher — plain httpx, no ScrapingBee credits.

Step-0 finding: PDFs at `https://www.consob.it/documents/...` are NOT
Radware-protected. Plain httpx with a desktop User-Agent + Italian
Accept-Language returns the file directly. We keep the 1 req/s + jitter
rate-limiter from phase 2 to stay polite.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import httpx
import structlog

from src.core.exceptions import ExternalServiceError
from src.core.settings import get_settings
from src.ingestion.amf.rate_limiter import RateLimiter, retry_with_backoff

_log = structlog.get_logger(__name__)

_MIN_PDF_BYTES = 1024


class ConsobPdfFetcher:
    """Download `documento d'offerta` PDFs atomically to disk."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: RateLimiter,
        *,
        data_dir: str | None = None,
        max_retries: int | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._rate_limiter = rate_limiter
        self._data_dir = Path(data_dir or settings.data_dir)
        self._max_retries = (
            max_retries if max_retries is not None else settings.poller_amf_max_retries
        )

    async def download(self, url: str, *, consob_ref: str, year: int) -> Path:
        """Fetch the PDF at `url` and place it under
        `${data_dir}/pdfs/it/{year}/{consob_ref}.pdf`. Atomic via
        `tempfile.mkstemp` + `os.replace`. Idempotent if the file already
        exists with non-zero size."""
        target_dir = self._data_dir / "pdfs" / "it" / str(year)
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / f"{consob_ref}.pdf"

        if final_path.exists() and final_path.stat().st_size > 0:
            _log.info("consob.pdf.cached", ref=consob_ref, path=str(final_path))
            return final_path

        await self._rate_limiter.acquire()
        content = await retry_with_backoff(
            lambda: self._get_bytes(url),
            max_retries=self._max_retries,
            service="consob-pdf",
        )

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{consob_ref}.",
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
            "consob.pdf.downloaded",
            ref=consob_ref,
            bytes=len(content),
            path=str(final_path),
        )
        return final_path

    async def _get_bytes(self, url: str) -> bytes:
        settings = get_settings()
        resp = await self._client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
                "Accept": "application/pdf,application/octet-stream,*/*",
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
                "Referer": "https://www.consob.it/web/area-pubblica/documenti-opa",
            },
            follow_redirects=True,
        )
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "").lower()
        if "pdf" not in ctype and len(resp.content) < _MIN_PDF_BYTES:
            raise ExternalServiceError(
                "consob-pdf",
                f"unexpected content-type {ctype!r} / short response ({len(resp.content)}b)",
            )
        _ = settings  # placeholder for future scrapingbee fallback toggle
        return resp.content
