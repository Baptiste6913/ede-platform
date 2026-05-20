"""Tests for src.ingestion.bafin.fetcher — deterministic URL derivation,
%PDF- magic validation, wrapper-scrape fallback on 404."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from src.core.exceptions import ExternalServiceError
from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.bafin.fetcher import BafinPdfFetcher, derive_pdf_url

_MINIMAL_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"X" * 200 + b"\n%%EOF\n"


# -------------------------- derive_pdf_url --------------------------


@pytest.mark.parametrize(
    ("wrapper", "expected"),
    [
        (
            "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.html?nn=151388",
            "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.pdf?__blob=publicationFile&v=1",
        ),
        (
            "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/kloeckner-co-se-2.html?nn=151388",
            "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/kloeckner-co-se-2.pdf?__blob=publicationFile&v=1",
        ),
        (
            # Without the nn query string still works.
            "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/foo.html",
            "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/foo.pdf?__blob=publicationFile&v=1",
        ),
    ],
)
def test_derive_pdf_url_canonical(wrapper: str, expected: str) -> None:
    assert derive_pdf_url(wrapper) == expected


def test_derive_pdf_url_passes_through_pdf_input() -> None:
    pdf = "https://example.com/foo.pdf"
    assert derive_pdf_url(pdf) == pdf


# -------------------------- download() happy path --------------------------


def _httpx_client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


async def test_download_happy_path_deterministic_url(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(
            200, content=_MINIMAL_PDF, headers={"content-type": "application/pdf"}
        )

    fetcher = BafinPdfFetcher(
        _httpx_client(handler),
        RateLimiter(100.0),
        data_dir=str(tmp_path),
    )
    p = await fetcher.download(
        "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.html?nn=151388",
        bafin_ref="BAFIN-DE000CBK1001-20260505",
        year=2026,
    )
    assert p.exists()
    assert p.read_bytes().startswith(b"%PDF-")
    # 1 single GET, the deterministic PDF URL — no wrapper fetch.
    assert len(calls) == 1
    assert "commerzbank.pdf" in calls[0]
    assert "__blob=publicationFile" in calls[0]


async def test_download_idempotent_when_already_on_disk(tmp_path: Path) -> None:
    target_dir = tmp_path / "pdfs" / "de" / "2026"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "BAFIN-X-20260101.pdf").write_bytes(_MINIMAL_PDF)

    # Handler raises if called — proves we never hit the network.
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected network call: {req.url}")

    fetcher = BafinPdfFetcher(
        _httpx_client(handler),
        RateLimiter(100.0),
        data_dir=str(tmp_path),
    )
    p = await fetcher.download(
        "https://www.bafin.de/foo.html?nn=1",
        bafin_ref="BAFIN-X-20260101",
        year=2026,
    )
    assert p.exists()


# -------------------------- fallback path --------------------------


async def test_download_falls_back_to_wrapper_scrape_on_404(tmp_path: Path) -> None:
    wrapper_html = (
        '<html><body><a class="FTpdf" '
        'href="https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/'
        'foo.pdf?__blob=publicationFile&v=2">Angebotsunterlage</a></body></html>'
    )

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if url.endswith(".pdf?__blob=publicationFile&v=1"):
            return httpx.Response(404, content=b"Not found")
        if "foo.html" in url:
            return httpx.Response(
                200, content=wrapper_html.encode("utf-8"), headers={"content-type": "text/html"}
            )
        if "v=2" in url:
            return httpx.Response(
                200, content=_MINIMAL_PDF, headers={"content-type": "application/pdf"}
            )
        return httpx.Response(500)

    fetcher = BafinPdfFetcher(
        _httpx_client(handler),
        RateLimiter(100.0),
        data_dir=str(tmp_path),
        max_retries=0,
    )
    p = await fetcher.download(
        "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/foo.html?nn=1",
        bafin_ref="BAFIN-DE000FOO0001-20260101",
        year=2026,
    )
    assert p.exists()
    assert p.read_bytes().startswith(b"%PDF-")


async def test_download_raises_when_neither_path_yields_pdf(tmp_path: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if url.endswith(".pdf?__blob=publicationFile&v=1"):
            return httpx.Response(404)
        if "bar.html" in url:
            # Wrapper has no PDF link → discover step itself raises.
            return httpx.Response(200, content=b"<html>no link</html>")
        return httpx.Response(500)

    fetcher = BafinPdfFetcher(
        _httpx_client(handler),
        RateLimiter(100.0),
        data_dir=str(tmp_path),
        max_retries=0,
    )
    with pytest.raises(ExternalServiceError):
        await fetcher.download(
            "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/bar.html?nn=1",
            bafin_ref="BAFIN-BAR-20260101",
            year=2026,
        )


async def test_download_rejects_non_pdf_body_then_falls_back(tmp_path: Path) -> None:
    """Even with 200 OK, a non-PDF body triggers fallback (defensive vs
    cached HTML on a stale BaFin URL)."""
    radware_html = b"<!DOCTYPE html>" + b"X" * 14000
    wrapper_html = (
        '<html><a href="https://www.bafin.de/foo_real.pdf?__blob=publicationFile&v=3">PDF</a>'
        "</html>"
    )

    state = {"v1_called": False, "real_pdf_called": False}

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if url.endswith(".pdf?__blob=publicationFile&v=1"):
            state["v1_called"] = True
            return httpx.Response(200, content=radware_html, headers={"content-type": "text/html"})
        if "foo.html" in url:
            return httpx.Response(
                200, content=wrapper_html.encode(), headers={"content-type": "text/html"}
            )
        if "v=3" in url:
            state["real_pdf_called"] = True
            return httpx.Response(
                200, content=_MINIMAL_PDF, headers={"content-type": "application/pdf"}
            )
        return httpx.Response(500)

    fetcher = BafinPdfFetcher(
        _httpx_client(handler),
        RateLimiter(100.0),
        data_dir=str(tmp_path),
        max_retries=0,
    )
    p = await fetcher.download(
        "https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/foo.html?nn=1",
        bafin_ref="BAFIN-FOO-20260201",
        year=2026,
    )
    assert state["v1_called"] is True
    assert state["real_pdf_called"] is True
    assert p.read_bytes().startswith(b"%PDF-")
