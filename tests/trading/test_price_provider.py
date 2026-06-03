"""Tests for the decision-time price provider (Phase 13) — no broker, no DB."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.trading.decision_engine import DealCandidate, reference_price
from src.trading.price_provider import YFinancePriceProvider


def _candidate(yahoo_ticker: str | None) -> DealCandidate:
    return DealCandidate(
        deal_id=1,
        target_name="Covivio Hotels",
        acquirer_name="ACQ",
        juridiction="FR",
        offer_price=50.0,
        p_completion=0.9,
        score_stars=5,
        symbol=None,
        exchange=None,
        isin="FR0000060303",
        yahoo_ticker=yahoo_ticker,
    )


async def test_no_ticker_returns_none():
    provider = YFinancePriceProvider()
    assert await provider.get_snapshot(_candidate(None)) is None


async def test_no_close_returns_none(monkeypatch):
    monkeypatch.setattr("src.pricing.yfinance_fetcher.get_close_eur", lambda *a, **k: None)
    provider = YFinancePriceProvider(as_of=date(2026, 6, 1))
    assert await provider.get_snapshot(_candidate("COVH.PA")) is None


async def test_close_builds_snapshot(monkeypatch):
    monkeypatch.setattr(
        "src.pricing.yfinance_fetcher.get_close_eur",
        lambda *a, **k: (Decimal("42.5"), date(2026, 5, 29)),
    )
    provider = YFinancePriceProvider(as_of=date(2026, 6, 1))
    snap = await provider.get_snapshot(_candidate("COVH.PA"))
    assert snap is not None
    assert snap.last == 42.5
    assert snap.close == 42.5
    assert snap.bid is None and snap.ask is None  # no broker quote
    assert snap.mid is None  # no bid/ask ⇒ engine falls back to last
    assert snap.price_source == "yfinance_close"
    # The decision engine's reference resolution works on this shape.
    assert reference_price(snap, "FR") == 42.5


@pytest.mark.parametrize("juridiction", ["FR", "DE", "IT"])
async def test_reference_price_resolves_across_jurisdictions(monkeypatch, juridiction):
    monkeypatch.setattr(
        "src.pricing.yfinance_fetcher.get_close_eur",
        lambda *a, **k: (Decimal("10.0"), date(2026, 5, 29)),
    )
    cand = _candidate("X.PA")
    snap = await YFinancePriceProvider(as_of=date(2026, 6, 1)).get_snapshot(cand)
    assert snap is not None
    assert reference_price(snap, juridiction) == 10.0
