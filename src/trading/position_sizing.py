"""Position sizing (Phase 8) — Kelly-fractional on live NetLiquidation.

Adapted from Finance-V4 `risk_manager.py`'s "guardrails applied last, never
bypassable" structure, with the formula swapped for the merger-arb Kelly
fractional specified in the Phase-8 brief.

Capital base (Step-0 decision #1): size off **live `NetLiquidation`** rather
than a hardcoded 100k, clamped to a sane band so a mis-read or a funded
account cannot blow up sizing:

    effective_capital = min(net_liquidation, 2_000_000)
    effective_capital = max(effective_capital, 50_000)

Guardrails (all non-bypassable, applied after Kelly):
- Kelly fraction 15% (conservative).
- Max single position 12% of effective capital.
- Min position €1000 (IBKR fee viability) → below ⇒ no trade.
- Max 5 concurrent positions → at cap ⇒ no trade.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import structlog

log = structlog.get_logger()

KELLY_FRACTION = 0.15
MAX_POSITION_PCT = 0.12
MIN_POSITION_EUR = 1_000.0
MAX_CONCURRENT_POSITIONS = 5
# Average historical M&A break loss (downside if the deal fails).
AVG_BREAK_LOSS = 0.15
# Effective-capital clamp band (decision #1).
CAPITAL_FLOOR = 50_000.0
CAPITAL_CAP = 2_000_000.0


@dataclass(frozen=True, slots=True)
class PositionSize:
    """Result of sizing one candidate. ``size_qty == 0`` ⇒ do not trade."""

    size_eur: float
    size_qty: int
    position_pct: float
    kelly_raw: float
    kelly_fractional: float
    expected_return_pct: float
    effective_capital: float
    reason: str  # "ok" | "no_edge" | "below_min" | "position_cap" | "bad_price"

    @property
    def tradeable(self) -> bool:
        return self.size_qty > 0 and self.reason == "ok"


def effective_capital(net_liquidation: float) -> float:
    """Clamp live NetLiquidation into the sizing band (decision #1)."""
    return max(min(net_liquidation, CAPITAL_CAP), CAPITAL_FLOOR)


def compute_kelly(p_completion: float, expected_return: float) -> tuple[float, float, float]:
    """Return (kelly_raw, kelly_fractional, position_pct).

    kelly_raw  = (p*er - (1-p)*|loss|) / er           (full Kelly)
    fractional = kelly_raw * 0.15                       (conservative)
    position_pct = clamp(fractional, 0, 0.12)           (hard cap)

    expected_return <= 0 means no edge, so all zero.
    """
    if expected_return <= 0:
        return 0.0, 0.0, 0.0
    kelly_raw = (
        p_completion * expected_return - (1.0 - p_completion) * AVG_BREAK_LOSS
    ) / expected_return
    kelly_fractional = kelly_raw * KELLY_FRACTION
    position_pct = max(0.0, min(MAX_POSITION_PCT, kelly_fractional))
    return kelly_raw, kelly_fractional, position_pct


def _result(
    reason: str,
    *,
    position_pct: float = 0.0,
    kelly_raw: float = 0.0,
    kelly_fractional: float = 0.0,
    expected_return: float = 0.0,
    cap: float = 0.0,
    size_eur: float = 0.0,
    size_qty: int = 0,
) -> PositionSize:
    return PositionSize(
        size_eur=size_eur,
        size_qty=size_qty,
        position_pct=position_pct,
        kelly_raw=kelly_raw,
        kelly_fractional=kelly_fractional,
        expected_return_pct=expected_return,
        effective_capital=cap,
        reason=reason,
    )


class PositionSizer:
    """Kelly-fractional sizing with non-bypassable guardrails."""

    def size(
        self,
        p_completion: float,
        expected_return: float,
        entry_price: float,
        net_liquidation: float,
        open_positions: int = 0,
    ) -> PositionSize:
        cap = effective_capital(net_liquidation)
        kelly_raw, kelly_fractional, position_pct = compute_kelly(p_completion, expected_return)

        if open_positions >= MAX_CONCURRENT_POSITIONS:
            return _result("position_cap", expected_return=expected_return, cap=cap)
        if entry_price <= 0:
            return _result("bad_price", expected_return=expected_return, cap=cap)
        if position_pct <= 0:
            return _result(
                "no_edge",
                kelly_raw=kelly_raw,
                kelly_fractional=kelly_fractional,
                expected_return=expected_return,
                cap=cap,
            )

        size_eur = position_pct * cap
        if size_eur < MIN_POSITION_EUR:
            return _result(
                "below_min",
                position_pct=position_pct,
                kelly_raw=kelly_raw,
                kelly_fractional=kelly_fractional,
                expected_return=expected_return,
                cap=cap,
                size_eur=size_eur,
            )

        size_qty = math.floor(size_eur / entry_price)
        if size_qty < 1:
            return _result(
                "below_min",
                position_pct=position_pct,
                kelly_raw=kelly_raw,
                kelly_fractional=kelly_fractional,
                expected_return=expected_return,
                cap=cap,
                size_eur=size_eur,
            )

        return _result(
            "ok",
            position_pct=position_pct,
            kelly_raw=kelly_raw,
            kelly_fractional=kelly_fractional,
            expected_return=expected_return,
            cap=cap,
            size_eur=size_qty * entry_price,
            size_qty=size_qty,
        )
