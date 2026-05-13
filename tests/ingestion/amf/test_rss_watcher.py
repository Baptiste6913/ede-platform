"""Tests for src.ingestion.amf.rss_watcher."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.amf.rss_watcher import TITLE_REGEX, RssWatcher


def test_regex_matches_expected_keywords() -> None:
    samples = [
        "Dépôt d'un projet d'offre publique d'achat",
        "Garantie de cours visant les actions de…",
        "Note d'information OPE",
        "OPRA initiée par X",
        "OPR-RO sur Omega",
        "OPA visant les actions de la société Algol",
    ]
    for s in samples:
        assert TITLE_REGEX.search(s), s


def test_regex_skips_unrelated_titles() -> None:
    samples = [
        "Communiqué de presse AMF sur les frais des OPCVM",
        "Décision AMF disciplinaire",
        "Communication relative au reporting MiFID",
    ]
    for s in samples:
        assert TITLE_REGEX.search(s) is None, s


async def test_rss_watcher_parses_three_known_patterns(rss_sample_bytes: bytes) -> None:
    """Synthetic RSS has 4 matches + 1 unrelated item."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=rss_sample_bytes))
    async with httpx.AsyncClient(transport=transport) as client:
        watcher = RssWatcher(client, RateLimiter(100.0), url="https://test.local/rss")
        items = await watcher.fetch()

    refs = [i.regulator_ref for i in items]

    assert len(items) == 4  # 4 matched, 1 OPCVM filtered out
    assert "AMF-2025-D-0421" in refs
    assert "AMF-2025-S-0033" in refs
    assert "AMF-2025-E-0019" in refs
    assert "AMF-2025-D-0099" in refs
    # Every matched item carries a keyword either in title or summary
    # (Omega OPR-RO mentions OPR only in the summary).
    for item in items:
        haystack = f"{item.title}\n{item.summary}".lower()
        assert any(
            kw in haystack
            for kw in ("opa", "ope", "opr", "garantie", "offre", "note d'information")
        ), item.title


async def test_rss_watcher_extracts_published_date(rss_sample_bytes: bytes) -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=rss_sample_bytes))
    async with httpx.AsyncClient(transport=transport) as client:
        watcher = RssWatcher(client, RateLimiter(100.0), url="https://test.local/rss")
        items = await watcher.fetch()

    item = next(i for i in items if i.regulator_ref == "AMF-2025-D-0421")
    assert item.published is not None
    assert item.published_date == date(2025, 5, 12)


async def test_rss_watcher_raises_on_persistent_5xx() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(500, content=b"err"))
    async with httpx.AsyncClient(transport=transport) as client:
        watcher = RssWatcher(
            client,
            RateLimiter(100.0),
            url="https://test.local/rss",
            max_retries=1,
        )
        # patch sleep to keep test fast
        from unittest.mock import AsyncMock, patch

        with (
            patch("src.ingestion.amf.rate_limiter.asyncio.sleep", new=AsyncMock()),
            pytest.raises(httpx.HTTPStatusError),
        ):
            await watcher.fetch()
