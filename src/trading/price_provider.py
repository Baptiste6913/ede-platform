"""Decision-time price provider (Phase 13) — decouples decision calc from IBKR.

The daily decision (reference price → spread → entry/stop → sizing) must be
computable **without** a live broker connection: IBKR paper is a downstream,
optional execution step (robustness — a Gateway outage must not stop decisions
being produced, persisted and notified).

This module supplies the reference-price snapshot the decision engine needs from
a non-broker source — the latest yfinance EOD close (the same source as the
Phase-11 premium backfill), converted to EUR and cached on disk.

The returned :class:`PriceSnapshot` is shaped like the IBKR one (no bid/ask,
``last == close``) so ``decision_engine.reference_price`` / ``compute_spread``
work unchanged: ``mid`` is ``None`` → callers fall back to ``last``. A ``None``
return means no usable price (the caller skips that candidate).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Protocol

import structlog

from src.trading.ibkr_client import PriceSnapshot

if TYPE_CHECKING:
    from src.trading.decision_engine import DealCandidate

log = structlog.get_logger()


class PriceProvider(Protocol):
    """A source of a decision-time reference-price snapshot for one candidate."""

    async def get_snapshot(self, candidate: DealCandidate) -> PriceSnapshot | None: ...


class YFinancePriceProvider:
    """Reference price from the latest yfinance EOD close (EUR) — no broker.

    ``as_of`` is injectable for deterministic tests; in production it defaults to
    today and the fetcher walks back ``max_lookback_days`` over weekends/holidays.
    """

    def __init__(self, *, max_lookback_days: int = 7, as_of: date | None = None) -> None:
        self._max_lookback_days = max_lookback_days
        self._as_of = as_of

    async def get_snapshot(self, candidate: DealCandidate) -> PriceSnapshot | None:
        ticker = candidate.yahoo_ticker
        if not ticker:
            log.info("price_provider_no_ticker", deal_id=candidate.deal_id)
            return None
        from src.pricing.yfinance_fetcher import get_close_eur

        target = self._as_of or date.today()
        priced = get_close_eur(ticker, target, max_lookback_days=self._max_lookback_days)
        if priced is None:
            log.info("price_provider_no_close", deal_id=candidate.deal_id, ticker=ticker)
            return None
        close = float(priced[0])
        return PriceSnapshot(
            bid=None,
            ask=None,
            last=close,
            close=close,
            market_data_type=0,
            price_source="yfinance_close",
        )
