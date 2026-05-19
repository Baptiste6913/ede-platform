"""End-to-end integration test for ConsobPoller.

Mocks both:
- ScrapingBee API (returns the captured Step-0 fixture page)
- PDF endpoint (returns a tiny synthetic Italian-PDF)

Asserts the full pipeline writes 50 deals + 50 events + downloads 50 PDFs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import fitz
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.models import Deal, Event, VendorApiUsage
from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.consob.fetcher import ConsobPdfFetcher
from src.ingestion.consob.poller import ConsobPoller
from src.ingestion.consob.scrapingbee_client import ScrapingBeeClient

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.integration

CONSOB_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "consob" / "documenti-opa-page1.html"
)


def _make_pdf_bytes() -> bytes:
    text = (
        "Documento di offerta — Banca Sistema Spa\n"
        "Offerente: Banca CF+ Credito Fondiario Spa\n"
        "Periodo di adesione: dal 11 maggio 2026 al 12 giugno 2026\n"
        "Il corrispettivo unitario e' pari a Euro 1,89 per azione\n"
        "Comunicazione n. 23-001 del 5 maggio 2026\n"
    )
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((50, 80), text, fontsize=10)
        return doc.tobytes()
    finally:
        doc.close()


@pytest.fixture
def fixture_html() -> str:
    return CONSOB_FIXTURE.read_text(encoding="utf-8")


def _scrapingbee_transport(html: str) -> httpx.MockTransport:
    """Mock the ScrapingBee API endpoint, returning the fixture HTML once
    then an empty page (forces iter_all to stop after page 1)."""
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                text=html,
                headers={"Spb-Cost": "1", "Spb-Initial-Status-Code": "200"},
            )
        # Second page → empty listing, stops iteration
        return httpx.Response(
            200,
            text='<ul class="consobResult"><li class="header">empty</li></ul>',
            headers={"Spb-Cost": "1", "Spb-Initial-Status-Code": "200"},
        )

    return httpx.MockTransport(handler)


def _pdf_transport(pdf_bytes: bytes) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=pdf_bytes, headers={"content-type": "application/pdf"})

    return httpx.MockTransport(handler)


async def test_run_backfill_creates_deals_and_downloads_pdfs(
    db_engine: object,
    db_clean: None,
    fixture_html: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.core.settings import get_settings

    get_settings.cache_clear()

    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    sb_http = httpx.AsyncClient(transport=_scrapingbee_transport(fixture_html))
    pdf_http = httpx.AsyncClient(transport=_pdf_transport(_make_pdf_bytes()))
    rl = RateLimiter(100.0)

    sb = ScrapingBeeClient(sf, http_client=sb_http)
    fetcher = ConsobPdfFetcher(pdf_http, rl, data_dir=str(tmp_path))
    poller = ConsobPoller(
        scrapingbee=sb,
        pdf_client=pdf_http,
        rate_limiter=rl,
        pdf_fetcher=fetcher,
        session_factory=sf,
    )

    try:
        result = await poller.run_backfill(max_pages=1)
    finally:
        await poller.aclose()

    # 50 fixture rows + 50 PDFs + 50 events
    assert result.discovered == 50
    assert result.created == 50
    assert result.pdf_downloaded == 50
    assert result.pdf_failed == 0
    assert result.credits_consumed == 1  # one listing call

    async with sf() as s:
        deals = (await s.execute(select(Deal).where(Deal.juridiction == "IT"))).scalars().all()
        assert len(deals) == 50
        banca_sistema = next(
            d for d in deals if d.regulator_ref == "CONSOB-opa_bancasistema_20260511"
        )
        assert banca_sistema.target_name == "Banca Sistema Spa"
        assert banca_sistema.deal_type == "opas"
        assert banca_sistema.pdf_path is not None

        events = (await s.execute(select(Event))).scalars().all()
        assert len(events) == 50
        assert all(e.event_type == "filing_consob" for e in events)

        usage = (await s.execute(select(VendorApiUsage))).scalars().all()
        assert len(usage) == 1
        assert usage[0].credits_cost == 1


async def test_run_incremental_stops_on_known_ref(
    db_engine: object,
    db_clean: None,
    fixture_html: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a full backfill, the next incremental tick must stop on the
    first known consob_ref and consume only one listing call."""
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.core.settings import get_settings

    get_settings.cache_clear()

    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]

    # Run backfill once
    sb_http_1 = httpx.AsyncClient(transport=_scrapingbee_transport(fixture_html))
    pdf_http_1 = httpx.AsyncClient(transport=_pdf_transport(_make_pdf_bytes()))
    rl = RateLimiter(100.0)
    sb_1 = ScrapingBeeClient(sf, http_client=sb_http_1)
    fetcher_1 = ConsobPdfFetcher(pdf_http_1, rl, data_dir=str(tmp_path))
    poller_1 = ConsobPoller(
        scrapingbee=sb_1,
        pdf_client=pdf_http_1,
        rate_limiter=rl,
        pdf_fetcher=fetcher_1,
        session_factory=sf,
    )
    try:
        await poller_1.run_backfill(max_pages=1)
    finally:
        await poller_1.aclose()

    # Now an incremental run
    sb_http_2 = httpx.AsyncClient(transport=_scrapingbee_transport(fixture_html))
    pdf_http_2 = httpx.AsyncClient(transport=_pdf_transport(_make_pdf_bytes()))
    sb_2 = ScrapingBeeClient(sf, http_client=sb_http_2)
    fetcher_2 = ConsobPdfFetcher(pdf_http_2, rl, data_dir=str(tmp_path))
    poller_2 = ConsobPoller(
        scrapingbee=sb_2,
        pdf_client=pdf_http_2,
        rate_limiter=rl,
        pdf_fetcher=fetcher_2,
        session_factory=sf,
    )
    try:
        result = await poller_2.run_incremental(max_pages=1)
    finally:
        await poller_2.aclose()

    assert result.stopped_on_known is True
    assert result.created == 0
    assert result.skipped == 0  # never reached upsert — broke out before
    assert result.discovered == 1  # the very first row was the known one
    assert result.credits_consumed == 1  # only 1 listing call
