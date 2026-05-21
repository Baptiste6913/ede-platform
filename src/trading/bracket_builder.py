"""Bracket order builder (Phase 8) — long-only LIMIT entry + server-side exits.

Adapted from Finance-V4 `bracket_order_builder.py`. EDE merger-arb is
**long-only**, so a bracket is:

  parent : LimitOrder BUY  (entry; default order type per success criterion 4)
  child 1: StopOrder  SELL (stop-loss; auto-attached)
  child 2: LimitOrder SELL (take-profit; auto-attached *iff* a target is set)

IBKR transmits the whole structure server-side once ``transmit=True`` on the
LAST leg; children reference the parent via ``parentId`` and IBKR cancels the
sibling when one child fills (OCA). Server-side stops execute at native speed —
Finance-V4's audit attributed **78% of historical drawdown to stop slippage**
from polling-based exits, which this design removes.

Pure module (no ib_async at build time) → fully unit-testable. ``to_ib_orders``
lazily maps specs to live ib_async Order objects at place-time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_TICK_SIZE = 0.01


@dataclass(frozen=True, slots=True)
class BracketLeg:
    """One IBKR order leg as plain data (SDK-free)."""

    order_id: int
    parent_id: int  # 0 for the parent leg
    action: str  # "BUY" | "SELL"
    qty: int
    order_type: str  # "LMT" | "STP"
    limit_price: float | None
    stop_price: float | None
    transmit: bool


def round_to_tick(price: float, tick_size: float = DEFAULT_TICK_SIZE) -> float:
    """Round to the nearest valid tick — IBKR rejects sub-tick prices."""
    if tick_size <= 0:
        return price
    return round(round(price / tick_size) * tick_size, 4)


def build_bracket(
    qty: int,
    entry_limit: float,
    stop_price: float,
    take_profit_price: float | None,
    parent_id: int,
    tick_size: float = DEFAULT_TICK_SIZE,
) -> list[BracketLeg]:
    """Build a long bracket: [parent BUY LMT, stop SELL STP, (opt) tp SELL LMT].

    ``parent_id`` is the IBKR client orderId for the parent; children use
    ``parent_id + 1`` (and ``+ 2`` for the optional take-profit). The caller
    reserves a contiguous block of orderIds and places the legs in order.

    Raises ``ValueError`` on degenerate brackets (qty/price <= 0, stop not
    below entry, take-profit not above entry).
    """
    if qty <= 0:
        raise ValueError(f"qty must be positive, got {qty}")
    if entry_limit <= 0:
        raise ValueError(f"entry_limit must be positive, got {entry_limit}")

    entry = round_to_tick(entry_limit, tick_size)
    stop = round_to_tick(stop_price, tick_size)
    if not 0 < stop < entry:
        raise ValueError(f"stop ({stop}) must be >0 and below entry ({entry})")

    has_tp = take_profit_price is not None
    tp = round_to_tick(take_profit_price, tick_size) if take_profit_price is not None else None
    if tp is not None and tp <= entry:
        raise ValueError(f"take_profit ({tp}) must be above entry ({entry})")

    legs = [
        BracketLeg(
            order_id=parent_id,
            parent_id=0,
            action="BUY",
            qty=qty,
            order_type="LMT",
            limit_price=entry,
            stop_price=None,
            transmit=False,
        ),
        BracketLeg(
            order_id=parent_id + 1,
            parent_id=parent_id,
            action="SELL",
            qty=qty,
            order_type="STP",
            limit_price=None,
            stop_price=stop,
            transmit=not has_tp,  # last leg transmits the whole bracket
        ),
    ]
    if tp is not None:
        legs.append(
            BracketLeg(
                order_id=parent_id + 2,
                parent_id=parent_id,
                action="SELL",
                qty=qty,
                order_type="LMT",
                limit_price=tp,
                stop_price=None,
                transmit=True,
            )
        )
    return legs


def to_ib_orders(legs: list[BracketLeg]) -> list[object]:
    """Map specs to live ib_async Order objects (lazy import, place in order)."""
    from ib_async import LimitOrder, StopOrder

    orders: list[object] = []
    for leg in legs:
        order: Any
        if leg.order_type == "LMT":
            assert leg.limit_price is not None
            order = LimitOrder(action=leg.action, totalQuantity=leg.qty, lmtPrice=leg.limit_price)
        elif leg.order_type == "STP":
            assert leg.stop_price is not None
            order = StopOrder(action=leg.action, totalQuantity=leg.qty, stopPrice=leg.stop_price)
        else:  # pragma: no cover — guarded by build_bracket
            raise ValueError(f"unknown order_type: {leg.order_type}")
        order.orderId = leg.order_id
        order.parentId = leg.parent_id
        order.transmit = leg.transmit
        orders.append(order)
    return orders
