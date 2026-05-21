"""EDE Phase 8 — paper trading on IBKR (FR/IT/DE merger-arb, long-only)."""

from src.trading.bracket_builder import BracketLeg, build_bracket, to_ib_orders
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
    "BracketLeg",
    "BrokerPosition",
    "IbkrClient",
    "PositionSize",
    "PositionSizer",
    "PriceSnapshot",
    "ResolvedTicker",
    "TickerResolver",
    "build_bracket",
    "compute_kelly",
    "effective_capital",
    "extract_isin",
    "normalize_name",
    "to_ib_orders",
]
