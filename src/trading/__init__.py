"""EDE Phase 8 — paper trading on IBKR (FR/IT/DE merger-arb, long-only)."""

from src.trading.ibkr_client import (
    AccountSnapshot,
    BrokerPosition,
    IbkrClient,
    PriceSnapshot,
)
from src.trading.position_sizing import (
    PositionSize,
    PositionSizer,
    compute_kelly,
    effective_capital,
)
from src.trading.ticker_resolver import (
    ResolvedTicker,
    TickerResolver,
    extract_isin,
    normalize_name,
)

__all__ = [
    "AccountSnapshot",
    "BrokerPosition",
    "IbkrClient",
    "PositionSize",
    "PositionSizer",
    "PriceSnapshot",
    "ResolvedTicker",
    "TickerResolver",
    "compute_kelly",
    "effective_capital",
    "extract_isin",
    "normalize_name",
]
