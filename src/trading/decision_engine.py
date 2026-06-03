"""Trade decision engine (Phase 8) — scored deals → TradeRequests.

For each pending, sufficiently-scored deal the daily run:

1. resolves a price reference from the (delayed) snapshot — **mid** for FR/DE,
   **last** for IT (BVME has no delayed bid/ask, Step-0 decision #3);
2. computes the merger-arb spread = (offer_price - reference) / reference and
   skips anything below ``min_spread_pct`` (no edge);
3. derives a LIMIT entry above the reference (jurisdiction-specific offset,
   decision #3), a protective stop, and a take-profit at the offer price;
4. sizes via Kelly-fractional (`PositionSizer`) on live NetLiquidation;
5. emits a :class:`TradeRequest`, flagged ``requires_approval`` while the
   ramp-up (first N trades manual) is active.

The scoring logic here is pure (`evaluate_candidate`); the orchestration that
pulls deals from the DB and prices from IBKR is injected, so the core is
unit-testable without a broker or database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog

from src.core.settings import Settings
from src.trading.ibkr_client import PriceSnapshot
from src.trading.position_sizing import PositionSizer

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class TradingConfig:
    """Tunables for the decision engine (sourced from Settings in production)."""

    min_spread_pct: float = 0.01
    entry_offset_quoted: float = 0.001
    entry_offset_last: float = 0.004
    stop_loss_pct: float = 0.10
    min_score_stars: int = 3
    rampup_required: int = 5


@dataclass(frozen=True, slots=True)
class DealCandidate:
    """Minimal deal view the engine needs (decoupled from the ORM row)."""

    deal_id: int
    target_name: str
    acquirer_name: str
    juridiction: str
    offer_price: float | None
    p_completion: float
    score_stars: int
    symbol: str | None
    exchange: str | None
    isin: str | None
    currency: str = "EUR"
    # Yahoo ticker (e.g. "COVH.PA") for the non-broker decision-time price
    # provider (Phase 13). Distinct from the IBKR (symbol, exchange) pair.
    yahoo_ticker: str | None = None


@dataclass(frozen=True, slots=True)
class TradeRequest:
    """A fully-specified long bracket the executor can submit (idempotent)."""

    trade_id: str
    deal_id: int
    deal_target: str
    deal_acquirer: str
    side: str  # always "BUY" (long-only merger arb)
    quantity: int
    symbol: str | None
    exchange: str | None
    isin: str | None
    currency: str
    limit_price: float
    stop_loss_price: float
    take_profit_price: float | None
    expected_p_completion: float
    expected_return_pct: float
    kelly_fractional_pct: float
    position_pct: float
    rationale: str
    requires_approval: bool
    price_source: str = "delayed_live"  # "delayed_live" | "frozen"


def reference_price(snapshot: PriceSnapshot, juridiction: str) -> float | None:
    """Reference price for spread/limit: mid for FR/DE, last for IT (no bid/ask)."""
    if juridiction == "IT":
        return snapshot.last or snapshot.mid
    return snapshot.mid or snapshot.last


def entry_limit_price(reference: float, juridiction: str, cfg: TradingConfig) -> float:
    """LIMIT entry slightly above reference (decision #3)."""
    offset = cfg.entry_offset_last if juridiction == "IT" else cfg.entry_offset_quoted
    return reference * (1.0 + offset)


def compute_spread(offer_price: float, reference: float) -> float:
    """Merger-arb spread = (offer - reference) / reference."""
    return (offer_price - reference) / reference


def evaluate_candidate(
    candidate: DealCandidate,
    snapshot: PriceSnapshot,
    net_liquidation: float,
    open_positions: int,
    rampup_validated: int,
    sizer: PositionSizer,
    cfg: TradingConfig,
) -> TradeRequest | None:
    """Pure core: produce a TradeRequest for one candidate, or None (logged)."""
    if candidate.score_stars < cfg.min_score_stars:
        return None
    if candidate.offer_price is None or candidate.offer_price <= 0:
        log.info("decision_skip_no_offer", deal_id=candidate.deal_id)
        return None

    reference = reference_price(snapshot, candidate.juridiction)
    if reference is None or reference <= 0:
        log.info("decision_skip_no_price", deal_id=candidate.deal_id)
        return None

    spread = compute_spread(candidate.offer_price, reference)
    if spread < cfg.min_spread_pct:
        log.info("decision_skip_thin_spread", deal_id=candidate.deal_id, spread=round(spread, 4))
        return None

    limit_price = entry_limit_price(reference, candidate.juridiction, cfg)
    sizing = sizer.size(
        p_completion=candidate.p_completion,
        expected_return=spread,
        entry_price=limit_price,
        net_liquidation=net_liquidation,
        open_positions=open_positions,
    )
    if not sizing.tradeable:
        log.info("decision_skip_sizing", deal_id=candidate.deal_id, reason=sizing.reason)
        return None

    stop_loss_price = limit_price * (1.0 - cfg.stop_loss_pct)
    take_profit_price = candidate.offer_price  # arb target = the offer
    requires_approval = rampup_validated < cfg.rampup_required

    rationale = (
        f"{candidate.target_name} merger-arb: p={candidate.p_completion:.2f}, "
        f"spread={spread:.1%}, Kelly_frac={sizing.kelly_fractional:.1%}, "
        f"{sizing.size_qty}@{limit_price:.2f} (offer {candidate.offer_price:.2f})"
    )

    return TradeRequest(
        trade_id=str(uuid.uuid4()),
        deal_id=candidate.deal_id,
        deal_target=candidate.target_name,
        deal_acquirer=candidate.acquirer_name,
        side="BUY",
        quantity=sizing.size_qty,
        symbol=candidate.symbol,
        exchange=candidate.exchange,
        isin=candidate.isin,
        currency=candidate.currency,
        limit_price=round(limit_price, 4),
        stop_loss_price=round(stop_loss_price, 4),
        take_profit_price=round(take_profit_price, 4),
        expected_p_completion=candidate.p_completion,
        expected_return_pct=round(spread, 6),
        kelly_fractional_pct=round(sizing.kelly_fractional, 6),
        position_pct=round(sizing.position_pct, 6),
        rationale=rationale,
        requires_approval=requires_approval,
        price_source=snapshot.price_source,
    )


class DecisionEngine:
    """Thin wrapper bundling a sizer + config for repeated candidate evaluation."""

    def __init__(
        self, sizer: PositionSizer | None = None, cfg: TradingConfig | None = None
    ) -> None:
        self.sizer = sizer or PositionSizer()
        self.cfg = cfg or TradingConfig()

    @classmethod
    def from_settings(cls, settings: Settings) -> DecisionEngine:
        cfg = TradingConfig(
            min_spread_pct=settings.trading_min_spread_pct,
            entry_offset_quoted=settings.trading_entry_offset_quoted,
            entry_offset_last=settings.trading_entry_offset_last,
            stop_loss_pct=settings.trading_stop_loss_pct,
            min_score_stars=settings.trading_min_score_stars,
            rampup_required=settings.trading_rampup_required,
        )
        return cls(cfg=cfg)

    def evaluate(
        self,
        candidate: DealCandidate,
        snapshot: PriceSnapshot,
        net_liquidation: float,
        open_positions: int,
        rampup_validated: int,
    ) -> TradeRequest | None:
        return evaluate_candidate(
            candidate,
            snapshot,
            net_liquidation,
            open_positions,
            rampup_validated,
            self.sizer,
            self.cfg,
        )
