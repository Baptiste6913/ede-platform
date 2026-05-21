"""EDE Phase 8 — paper trading on IBKR (FR/IT/DE merger-arb, long-only)."""

from src.trading.bracket_builder import BracketLeg, build_bracket, to_ib_orders
from src.trading.decision_engine import (
    DealCandidate,
    DecisionEngine,
    TradeRequest,
    TradingConfig,
    evaluate_candidate,
)
from src.trading.executor import TradeExecutor
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
from src.trading.safeguards import (
    KillSwitch,
    SystemStateStore,
    cooldown_active,
    daily_loss_breached,
    position_cap_reached,
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
    "DealCandidate",
    "DecisionEngine",
    "IbkrClient",
    "KillSwitch",
    "PositionSize",
    "PositionSizer",
    "PriceSnapshot",
    "ResolvedTicker",
    "SystemStateStore",
    "TickerResolver",
    "TradeExecutor",
    "TradeRequest",
    "TradingConfig",
    "build_bracket",
    "compute_kelly",
    "cooldown_active",
    "daily_loss_breached",
    "effective_capital",
    "evaluate_candidate",
    "extract_isin",
    "normalize_name",
    "position_cap_reached",
    "to_ib_orders",
]
