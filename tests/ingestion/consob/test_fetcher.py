"""Tests for src.ingestion.consob.fetcher — PDF-magic validation +
ScrapingBee fallback when Radware blocks direct httpx (Step-9 finding)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

from src.core.exceptions import ExternalServiceError
from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.consob.fetcher import ConsobPdfFetcher

if TYPE_CHECKING:
    pass


_MINIMAL_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"X" * 200 + b"\n%%EOF\n"
_RADWARE_HTML = (
    b'<!DOCTYPE html>\n<html lang="en">\n<head><title>Radware Captcha</title></head>'
    + b"<body>"
    + b"X" * 14000
    + b"</body></html>"
)


def _httpx_client(body: bytes, content_type: str = "application/pdf") -> httpx.AsyncClient:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": content_type})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_download_accepts_valid_pdf(tmp_path: Path) -> None:
    fetcher = ConsobPdfFetcher(
        _httpx_client(_MINIMAL_PDF),
        RateLimiter(100.0),
        data_dir=str(tmp_path),
    )
    p = await fetcher.download(
        "https://www.consob.it/documents/x/opa_test_20260519.pdf/uuid",
        consob_ref="CONSOB-opa_test_20260519",
        year=2026,
    )
    assert p.exists()
    assert p.read_bytes().startswith(b"%PDF-")


async def test_download_rejects_non_pdf_body_without_fallback(tmp_path: Path) -> None:
    """Radware HTML captcha disguised at .pdf URL — must raise, not silently
    save 15 KB of HTML."""
    fetcher = ConsobPdfFetcher(
        _httpx_client(_RADWARE_HTML, content_type="text/html"),
        RateLimiter(100.0),
        data_dir=str(tmp_path),
    )
    with pytest.raises(ExternalServiceError):
        await fetcher.download(
            "https://www.consob.it/documents/x/opa_test.pdf/uuid",
            consob_ref="CONSOB-opa_test_radware",
            year=2026,
        )


@pytest.mark.integration
async def test_download_falls_back_to_scrapingbee_when_direct_returns_html(
    db_engine: object,
    db_clean: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When direct httpx returns Radware HTML, the fetcher must retry via
    ScrapingBee and accept the resulting PDF body."""
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.core.settings import get_settings
    from src.ingestion.consob.scrapingbee_client import ScrapingBeeClient

    get_settings.cache_clear()
    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]

    def sb_handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_MINIMAL_PDF,
            headers={"Spb-Cost": "1", "content-type": "application/pdf"},
        )

    sb_http = httpx.AsyncClient(transport=httpx.MockTransport(sb_handler))
    sb = ScrapingBeeClient(sf, http_client=sb_http)

    fetcher = ConsobPdfFetcher(
        _httpx_client(_RADWARE_HTML, content_type="text/html"),
        RateLimiter(100.0),
        data_dir=str(tmp_path),
        scrapingbee=sb,
    )
    p = await fetcher.download(
        "https://www.consob.it/documents/x/opa_fallback.pdf/uuid",
        consob_ref="CONSOB-opa_fallback",
        year=2026,
    )
    await sb.aclose()
    assert p.exists()
    assert p.read_bytes().startswith(b"%PDF-")
