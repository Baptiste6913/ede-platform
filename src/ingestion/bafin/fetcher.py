"""BaFin PDF fetcher — deterministic URL with wrapper-scrape fallback.

Step-0 finding (2026-05-19): the Angebotsunterlage PDF URL is a pure
function of the wrapper URL. Replace `.html?nn=…` with
`.pdf?__blob=publicationFile&v=1` and you get the file directly. This
saves one HTTP round-trip per deal vs always loading the wrapper.

When the deterministic URL 404s (e.g. amended documents at `v=2`,
`v=3`…), we fall back to scraping the wrapper page and following the
PDF link found in it. Both paths are direct httpx — no ScrapingBee.

All responses are validated by `%PDF-` magic-byte check (Phase-4
lesson learned: an HTTP 200 on a `.pdf` URL does not guarantee actual
PDF bytes).
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from pathlib import Path

import httpx
import structlog
from bs4 import BeautifulSoup

from src.core.exceptions import ExternalServiceError
from src.core.settings import get_settings
from src.ingestion.amf.rate_limiter import RateLimiter, retry_with_backoff

_log = structlog.get_logger(__name__)

_PDF_MAGIC = b"%PDF-"
_WRAPPER_TO_PDF_RE = re.compile(r"\.html(\?nn=[^&]*)?(?=$|&)")
_DEFAULT_PDF_SUFFIX = ".pdf?__blob=publicationFile&v=1"

_FETCHER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream,text/html;q=0.5,*/*;q=0.3",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
    "Referer": "https://www.bafin.de/",
}


def derive_pdf_url(wrapper_url: str) -> str:
    """Compute the deterministic PDF URL from a wrapper HTML URL.

    Example:
        https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.html?nn=151388
        → https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.pdf?__blob=publicationFile&v=1
    """
    # The match removes the .html plus any single ?nn=... query param appended
    # to the .html (BaFin doesn't combine other params with nn).
    if ".html" not in wrapper_url:
        # Already a PDF URL or something else — return unchanged.
        return wrapper_url
    base = re.sub(r"\.html(?:\?nn=[^&]*)?$", "", wrapper_url)
    return base + _DEFAULT_PDF_SUFFIX


class BafinPdfFetcher:
    """Download Angebotsunterlage PDFs atomically to disk."""

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

    async def download(
        self,
        wrapper_url: str,
        *,
        bafin_ref: str,
        year: int,
    ) -> Path:
        """Fetch the PDF for the offer and write it to
        `${data_dir}/pdfs/de/{year}/{bafin_ref}.pdf` (atomic).

        Tries the deterministic URL first; falls back to wrapper-scrape
        on 404. Idempotent if the file already exists with non-zero size.
        """
        target_dir = self._data_dir / "pdfs" / "de" / str(year)
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / f"{bafin_ref}.pdf"

        if final_path.exists() and final_path.stat().st_size > 0:
            _log.info("bafin.pdf.cached", ref=bafin_ref, path=str(final_path))
            return final_path

        pdf_url = derive_pdf_url(wrapper_url)
        content = await self._try_download(pdf_url, bafin_ref=bafin_ref)
        if content is None:
            _log.info(
                "bafin.pdf.fallback_wrapper",
                ref=bafin_ref,
                wrapper=wrapper_url,
            )
            pdf_url = await self._discover_pdf_via_wrapper(wrapper_url)
            content = await self._try_download(pdf_url, bafin_ref=bafin_ref)
            if content is None:
                raise ExternalServiceError(
                    "bafin-pdf",
                    f"both deterministic + wrapper paths returned non-PDF for {bafin_ref}",
                )

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{bafin_ref}.",
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
            "bafin.pdf.downloaded",
            ref=bafin_ref,
            bytes=len(content),
            path=str(final_path),
        )
        return final_path

    async def _try_download(self, url: str, *, bafin_ref: str) -> bytes | None:
        """Returns the bytes if 200 + valid %PDF-, else None on 404 or
        non-PDF body. Raises for other HTTP errors."""
        await self._rate_limiter.acquire()
        try:
            content = await retry_with_backoff(
                lambda: self._get_bytes(url),
                max_retries=self._max_retries,
                service="bafin-pdf",
            )
        except ExternalServiceError as exc:
            # 404 is a fall-back trigger, not a hard fail.
            if "404" in str(exc):
                _log.info("bafin.pdf.404", ref=bafin_ref, url=url)
                return None
            raise
        if not content.startswith(_PDF_MAGIC):
            _log.info(
                "bafin.pdf.non_pdf_body",
                ref=bafin_ref,
                url=url,
                bytes=len(content),
            )
            return None
        return content

    async def _get_bytes(self, url: str) -> bytes:
        resp = await self._client.get(url, headers=_FETCHER_HEADERS, follow_redirects=True)
        if resp.status_code == httpx.codes.NOT_FOUND:
            raise ExternalServiceError("bafin-pdf", "404 Not Found", status_code=404)
        resp.raise_for_status()
        return resp.content

    async def _discover_pdf_via_wrapper(self, wrapper_url: str) -> str:
        """Scrape the wrapper HTML page to find the actual PDF link."""
        resp = await self._client.get(wrapper_url, headers=_FETCHER_HEADERS, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if ".pdf" in href and "blob=publicationFile" in href:
                if not href.startswith("http"):
                    href = "https://www.bafin.de" + href
                return str(href)
        raise ExternalServiceError(
            "bafin-pdf",
            f"no PDF link found inside wrapper {wrapper_url}",
        )
