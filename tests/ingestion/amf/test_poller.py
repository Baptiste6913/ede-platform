"""End-to-end test for the AMF poller (HTTP mocked, real DB)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.models import Deal, Event
from src.ingestion.amf.poller import AmfPoller
from src.ingestion.amf.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _make_mock_transport(
    rss_bytes: bytes,
    detail_html: str,
    pdf_bytes: bytes,
) -> httpx.MockTransport:
    """Route requests by URL pattern → fixture content."""

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "flux-rss" in url or url.endswith("/rss"):
            return httpx.Response(
                200, content=rss_bytes, headers={"content-type": "application/rss+xml"}
            )
        if "bdif.amf-france.org" in url:
            return httpx.Response(
                200, content=pdf_bytes, headers={"content-type": "application/pdf"}
            )
        # Anything else is an AMF detail page.
        return httpx.Response(200, text=detail_html)

    return httpx.MockTransport(handler)


async def test_poller_run_once_creates_deals_with_events(
    db_engine: object,
    db_clean: None,
    rss_sample_bytes: bytes,
    amf_detail_page_html: str,
    synthetic_pdf_bytes: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean  # explicit truncate-on-teardown
    # Point AMF poller storage + RSS URL at our fixtures.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AMF_RSS_URL", "https://test.local/rss")

    from src.core.settings import get_settings

    get_settings.cache_clear()

    transport = _make_mock_transport(rss_sample_bytes, amf_detail_page_html, synthetic_pdf_bytes)
    client = httpx.AsyncClient(transport=transport, base_url="https://test.local")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    rl = RateLimiter(100.0)  # effectively no rate limit for the test
    poller = AmfPoller(
        client=client,
        rate_limiter=rl,
        session_factory=session_factory,
    )
    # Override the bdif_fetcher's rate limiter so it doesn't share the same
    # state across instances (purely cosmetic — fresh limiter per test).
    poller._bdif_fetcher._rate_limiter = rl
    poller._rss_watcher._rate_limiter = rl

    try:
        result = await poller.run_once()
    finally:
        await poller.aclose()

    # 4 matched in the RSS sample (one is filtered as unrelated)
    assert result.matched == 4
    assert result.created == 4
    assert result.skipped == 0
    assert result.pdf_downloaded == 4

    async with session_factory() as session:
        deals = (
            (await session.execute(select(Deal).where(Deal.juridiction == "FR"))).scalars().all()
        )
        assert len(deals) == 4
        refs = {d.regulator_ref for d in deals}
        assert "AMF-2025-D-0421" in refs
        assert "AMF-2025-S-0033" in refs
        assert "AMF-2025-E-0019" in refs
        assert "AMF-2025-D-0099" in refs

        events = (await session.execute(select(Event))).scalars().all()
        assert len(events) == 4
        assert all(e.event_type == "filing_amf" for e in events)


async def test_poller_second_run_is_idempotent(
    db_engine: object,
    db_clean: None,
    rss_sample_bytes: bytes,
    amf_detail_page_html: str,
    synthetic_pdf_bytes: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.core.settings import get_settings

    get_settings.cache_clear()

    transport = _make_mock_transport(rss_sample_bytes, amf_detail_page_html, synthetic_pdf_bytes)
    client = httpx.AsyncClient(transport=transport, base_url="https://test.local")
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    rl = RateLimiter(100.0)
    poller = AmfPoller(client=client, rate_limiter=rl, session_factory=session_factory)
    poller._bdif_fetcher._rate_limiter = rl
    poller._rss_watcher._rate_limiter = rl

    try:
        first = await poller.run_once()
        second = await poller.run_once()
    finally:
        await poller.aclose()

    assert first.created == 4
    assert second.created == 0
    assert second.skipped == 4


async def test_poller_handles_missing_bdif_link(
    db_engine: object,
    db_clean: None,
    rss_sample_bytes: bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RSS items whose detail page has no BDIF link still produce deal rows."""
    _ = db_clean
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from src.core.settings import get_settings

    get_settings.cache_clear()

    no_link_html = "<html><body>No documents attached yet.</body></html>"

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "flux-rss" in url or url.endswith("/rss"):
            return httpx.Response(200, content=rss_sample_bytes)
        return httpx.Response(200, text=no_link_html)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://test.local")
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    rl = RateLimiter(100.0)
    poller = AmfPoller(client=client, rate_limiter=rl, session_factory=session_factory)
    poller._bdif_fetcher._rate_limiter = rl
    poller._rss_watcher._rate_limiter = rl

    # Stub asyncio.sleep so backoff doesn't slow the test.
    monkeypatch.setattr("src.ingestion.amf.rate_limiter.asyncio.sleep", AsyncMock())

    try:
        result = await poller.run_once()
    finally:
        await poller.aclose()

    assert result.matched == 4
    assert result.created == 4
    assert result.pdf_downloaded == 0
