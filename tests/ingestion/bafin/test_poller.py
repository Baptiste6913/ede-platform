"""End-to-end integration test for BafinPoller.

Mocks the HTTP layer with three URL families:
- the listing page (returns the captured Step-0 fixture)
- the deterministic PDF URL pattern (returns a synthetic %PDF-)
- everything else (404)

Asserts the full pipeline writes deals + filing_bafin events + downloads
PDFs, and that incremental mode stops on the first known ref.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import fitz
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.models import Deal, Event
from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.bafin.discovery import BafinDiscoveryClient
from src.ingestion.bafin.fetcher import BafinPdfFetcher
from src.ingestion.bafin.poller import BafinPoller

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.integration

LISTING_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "bafin" / "angebotsunterlagen-listing.html"
)


def _make_pdf_bytes() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text(
            (50, 80),
            (
                "Übernahmeangebot\n"
                "Bieter: ACME GmbH\nZielgesellschaft: Foo AG\n"
                "Annahmefrist: vom 01. März 2026 bis zum 30. April 2026\n"
                "Angebotspreis: EUR 10,00\n"
            ),
            fontsize=10,
        )
        return doc.tobytes()
    finally:
        doc.close()


@pytest.fixture
def listing_html() -> str:
    return LISTING_FIXTURE.read_text(encoding="utf-8")


def _transport(listing_html: str, pdf_bytes: bytes) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "angebotsunterlagen_node.html" in url:
            return httpx.Response(200, text=listing_html)
        if ".pdf?__blob=publicationFile" in url:
            return httpx.Response(
                200, content=pdf_bytes, headers={"content-type": "application/pdf"}
            )
        # Wrapper fallback: synthetic HTML with the deterministic PDF embedded.
        if ".html?nn=" in url:
            embedded = (
                '<html><a href="https://www.bafin.de/foo.pdf?__blob=publicationFile&v=1">'
                "PDF</a></html>"
            )
            return httpx.Response(
                200, content=embedded.encode(), headers={"content-type": "text/html"}
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_run_backfill_creates_deals_and_downloads_pdfs(
    db_engine: object,
    db_clean: None,
    listing_html: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.core.settings import get_settings

    get_settings.cache_clear()

    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    http = httpx.AsyncClient(transport=_transport(listing_html, _make_pdf_bytes()))
    rl = RateLimiter(100.0)
    discovery = BafinDiscoveryClient(http)
    fetcher = BafinPdfFetcher(http, rl, data_dir=str(tmp_path))
    poller = BafinPoller(
        http_client=http,
        rate_limiter=rl,
        discovery=discovery,
        pdf_fetcher=fetcher,
        session_factory=sf,
    )

    try:
        # Far-past `since` so the full fixture (2016→2026) is in scope.
        result = await poller.run_backfill(since=date(2010, 1, 1))
    finally:
        await poller.aclose()

    assert result.discovered >= 200
    assert result.created == result.discovered
    assert result.pdf_downloaded == result.discovered
    assert result.pdf_failed == 0

    async with sf() as s:
        deals = (await s.execute(select(Deal).where(Deal.juridiction == "DE"))).scalars().all()
        assert len(deals) == result.discovered
        commerz = next(
            (d for d in deals if d.regulator_ref == "BAFIN-DE000CBK1001-20260505"),
            None,
        )
        assert commerz is not None
        assert commerz.target_name == "COMMERZBANK Aktiengesellschaft"
        assert commerz.deal_type == "opa_volontaire_totalitaria"
        assert commerz.pdf_path is not None

        events = (await s.execute(select(Event))).scalars().all()
        assert len(events) == len(deals)
        assert all(e.event_type == "filing_bafin" for e in events)


async def test_run_incremental_stops_on_known_ref(
    db_engine: object,
    db_clean: None,
    listing_html: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a backfill, the next incremental tick must stop on the first
    known bafin_ref."""
    _ = db_clean
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.core.settings import get_settings

    get_settings.cache_clear()
    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]

    # First — backfill.
    http1 = httpx.AsyncClient(transport=_transport(listing_html, _make_pdf_bytes()))
    rl = RateLimiter(100.0)
    poller1 = BafinPoller(
        http_client=http1,
        rate_limiter=rl,
        discovery=BafinDiscoveryClient(http1),
        pdf_fetcher=BafinPdfFetcher(http1, rl, data_dir=str(tmp_path)),
        session_factory=sf,
    )
    try:
        await poller1.run_backfill(since=date(2010, 1, 1))
    finally:
        await poller1.aclose()

    # Then — incremental run.
    http2 = httpx.AsyncClient(transport=_transport(listing_html, _make_pdf_bytes()))
    poller2 = BafinPoller(
        http_client=http2,
        rate_limiter=rl,
        discovery=BafinDiscoveryClient(http2),
        pdf_fetcher=BafinPdfFetcher(http2, rl, data_dir=str(tmp_path)),
        session_factory=sf,
    )
    try:
        result = await poller2.run_incremental(since=date(2010, 1, 1))
    finally:
        await poller2.aclose()

    assert result.stopped_on_known is True
    assert result.discovered == 1  # first row was the known one
    assert result.created == 0
