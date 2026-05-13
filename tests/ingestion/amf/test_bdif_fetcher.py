"""Tests for src.ingestion.amf.bdif_fetcher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.ingestion.amf.bdif_fetcher import BdifFetcher, BdifLink
from src.ingestion.amf.rate_limiter import RateLimiter


def test_bdif_link_from_url_parses_year_ref_hash() -> None:
    url = (
        "https://bdif.amf-france.org/back/api/v1/documents/"
        "2025/AMF-2025-D-0421/AbCdEfGh1234567890QrStUv-XYZ_aaaa.pdf"
    )
    link = BdifLink.from_url(url)
    assert link is not None
    assert link.url == url
    assert link.year == 2025
    assert link.regulator_ref == "AMF-2025-D-0421"
    assert link.hash64 == "AbCdEfGh1234567890QrStUv-XYZ_aaaa"


def test_bdif_link_from_url_returns_none_on_non_bdif() -> None:
    assert BdifLink.from_url("https://example.test/not-a-bdif.pdf") is None


async def test_discover_bdif_url_finds_link_in_detail_page(
    amf_detail_page_html: str, tmp_path: Path
) -> None:
    detail_url = "https://www.amf-france.org/fr/details/AMF-2025-D-0421"

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url == httpx.URL(detail_url)
        return httpx.Response(200, text=amf_detail_page_html)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = BdifFetcher(client, RateLimiter(100.0), data_dir=str(tmp_path))
        link = await fetcher.discover_bdif_url(detail_url)

    assert link is not None
    assert link.regulator_ref == "AMF-2025-D-0421"


async def test_discover_bdif_url_returns_none_when_absent(tmp_path: Path) -> None:
    detail_url = "https://www.amf-france.org/fr/details/X"
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, text="<html>no link here</html>")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = BdifFetcher(client, RateLimiter(100.0), data_dir=str(tmp_path))
        link = await fetcher.discover_bdif_url(detail_url)
    assert link is None


async def test_download_writes_atomically_and_returns_path(
    tmp_path: Path, synthetic_pdf_bytes: bytes
) -> None:
    bdif_url = (
        "https://bdif.amf-france.org/back/api/v1/documents/"
        "2025/AMF-2025-D-0421/AbCdEfGh1234567890QrStUv-XYZ_aaaa.pdf"
    )

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=synthetic_pdf_bytes,
            headers={"content-type": "application/pdf"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = BdifFetcher(client, RateLimiter(100.0), data_dir=str(tmp_path))
        link = BdifLink.from_url(bdif_url)
        assert link is not None
        path = await fetcher.download(link)

    # Final path matches the documented layout: {data_dir}/pdfs/fr/{year}/{ref}.pdf
    expected = tmp_path / "pdfs" / "fr" / "2025" / "AMF-2025-D-0421.pdf"
    assert path == expected
    assert expected.exists()
    assert expected.read_bytes() == synthetic_pdf_bytes

    # No leftover .part files (atomic rename succeeded).
    leftovers = list(expected.parent.glob("*.part"))
    assert leftovers == [], leftovers


async def test_download_is_idempotent_when_file_exists(
    tmp_path: Path, synthetic_pdf_bytes: bytes
) -> None:
    bdif_url = (
        "https://bdif.amf-france.org/back/api/v1/documents/"
        "2025/AMF-2025-D-0421/AbCdEfGh1234567890QrStUv-XYZ_aaaa.pdf"
    )
    # Pre-populate the target path.
    target = tmp_path / "pdfs" / "fr" / "2025" / "AMF-2025-D-0421.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(synthetic_pdf_bytes)

    transport = httpx.MockTransport(lambda req: httpx.Response(500, text="should not be called"))
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = BdifFetcher(client, RateLimiter(100.0), data_dir=str(tmp_path))
        link = BdifLink.from_url(bdif_url)
        assert link is not None
        path = await fetcher.download(link)

    assert path == target
    assert path.read_bytes() == synthetic_pdf_bytes


async def test_download_year_override_uses_announcement_year(
    tmp_path: Path, synthetic_pdf_bytes: bytes
) -> None:
    """BDIF URL year may differ from the deal announcement year — override wins."""
    bdif_url = (
        "https://bdif.amf-france.org/back/api/v1/documents/"
        "2025/AMF-2025-D-0421/AbCdEfGh1234567890QrStUv-XYZ_aaaa.pdf"
    )
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, content=synthetic_pdf_bytes, headers={"content-type": "application/pdf"}
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = BdifFetcher(client, RateLimiter(100.0), data_dir=str(tmp_path))
        link = BdifLink.from_url(bdif_url)
        assert link is not None
        path = await fetcher.download(link, year=2024)
    assert path == tmp_path / "pdfs" / "fr" / "2024" / "AMF-2025-D-0421.pdf"


async def test_download_rejects_non_pdf_short_response(tmp_path: Path) -> None:
    bdif_url = (
        "https://bdif.amf-france.org/back/api/v1/documents/"
        "2025/AMF-2025-D-0421/AbCdEfGh1234567890QrStUv-XYZ_aaaa.pdf"
    )
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, content=b"<html>error page</html>", headers={"content-type": "text/html"}
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = BdifFetcher(client, RateLimiter(100.0), data_dir=str(tmp_path))
        link = BdifLink.from_url(bdif_url)
        assert link is not None

        with patch("src.ingestion.amf.rate_limiter.asyncio.sleep", new=AsyncMock()):
            from src.core.exceptions import ExternalServiceError

            with pytest.raises(ExternalServiceError):
                await fetcher.download(link)
