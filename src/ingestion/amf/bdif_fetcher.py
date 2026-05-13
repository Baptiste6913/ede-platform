"""BDIF PDF fetcher.

Resolves the BDIF PDF URL from an AMF detail page (the RSS item link) and
downloads it atomically to:

    {data_dir}/pdfs/fr/{year}/{regulator_ref}.pdf

Atomic write: write to a `.part` temp file in the same directory then
`os.replace()` to the final path. This avoids partial files on crash.

URL pattern (CLAUDE.md):
    https://bdif.amf-france.org/back/api/v1/documents/{ANNEE}/{REF}/{HASH64}.pdf

The HASH64 part is not predictable — we have to fetch the AMF detail page
and scrape the BDIF link out of it. The detail page HTML is generally a
JavaScript SPA that exposes the link via a `<meta>`, `<a href>` or a JSON
blob; we use a permissive regex.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx
import structlog

from src.core.exceptions import ExternalServiceError
from src.core.settings import get_settings
from src.ingestion.amf.rate_limiter import RateLimiter, retry_with_backoff

_log = structlog.get_logger(__name__)

# Permissive regex: BDIF URLs always have the back/api/v1/documents prefix.
_BDIF_URL_REGEX: Final[re.Pattern[str]] = re.compile(
    r"https?://bdif\.amf-france\.org/back/api/v1/documents/"
    r"(?P<year>\d{4})/(?P<ref>[^/\"\s]+)/(?P<hash64>[A-Za-z0-9_-]{20,128})\.pdf",
)

# Below this size a response is suspiciously short for a real PDF (real notes
# are usually >10 KB even for short filings). Treated as a transport error.
_MIN_PDF_BYTES: Final[int] = 1024


@dataclass(frozen=True, slots=True)
class BdifLink:
    """A parsed BDIF PDF URL."""

    url: str
    year: int
    regulator_ref: str
    hash64: str

    @classmethod
    def from_url(cls, url: str) -> BdifLink | None:
        m = _BDIF_URL_REGEX.search(url)
        if not m:
            return None
        return cls(
            url=url,
            year=int(m.group("year")),
            regulator_ref=m.group("ref"),
            hash64=m.group("hash64"),
        )


class BdifFetcher:
    """Discovers BDIF PDF links from AMF detail pages and downloads them."""

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

    async def discover_bdif_url(self, detail_page_url: str) -> BdifLink | None:
        """Fetch the AMF detail page and scrape the first BDIF URL.

        Returns None if no BDIF link is found (some AMF pages don't yet have
        a downloadable note attached).
        """
        await self._rate_limiter.acquire()
        body = await retry_with_backoff(
            lambda: self._get_text(detail_page_url),
            max_retries=self._max_retries,
            service="amf-detail",
        )
        match = _BDIF_URL_REGEX.search(body)
        if match is None:
            _log.info("amf.bdif.no_link", page=detail_page_url)
            return None
        return BdifLink.from_url(match.group(0))

    async def download(self, link: BdifLink, *, year: int | None = None) -> Path:
        """Download the PDF and atomically place it on disk.

        `year` overrides the year from the URL — useful when the BDIF URL year
        differs from the deal announcement year (rare but possible for late
        filings). Defaults to the URL's year.
        """
        target_year = year if year is not None else link.year
        target_dir = self._data_dir / "pdfs" / "fr" / str(target_year)
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / f"{link.regulator_ref}.pdf"

        if final_path.exists() and final_path.stat().st_size > 0:
            _log.info(
                "amf.pdf.already_cached",
                ref=link.regulator_ref,
                path=str(final_path),
            )
            return final_path

        await self._rate_limiter.acquire()
        content = await retry_with_backoff(
            lambda: self._get_bytes(link.url),
            max_retries=self._max_retries,
            service="amf-pdf",
        )

        # Atomic write: tmp file in the same directory, then replace.
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{link.regulator_ref}.",
            suffix=".pdf.part",
            dir=str(target_dir),
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            os.replace(tmp_name, final_path)
        except Exception:
            # Best-effort cleanup; surface the original error.
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

        _log.info(
            "amf.pdf.downloaded",
            ref=link.regulator_ref,
            bytes=len(content),
            path=str(final_path),
        )
        return final_path

    async def _get_text(self, url: str) -> str:
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.text

    async def _get_bytes(self, url: str) -> bytes:
        resp = await self._client.get(url)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "pdf" not in ctype.lower() and len(resp.content) < _MIN_PDF_BYTES:
            raise ExternalServiceError(
                "amf-pdf",
                f"unexpected content-type {ctype!r} or short response ({len(resp.content)} bytes)",
            )
        return resp.content


def _resolve_data_dir_for(juridiction_code: str, year: int) -> Path:
    """Helper exposed for tests."""
    return Path(get_settings().data_dir) / "pdfs" / juridiction_code.lower() / str(year)
