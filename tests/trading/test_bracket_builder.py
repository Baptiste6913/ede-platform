"""Unit tests for the long-only bracket builder (pure)."""

from __future__ import annotations

import pytest

from src.trading.bracket_builder import (
    BracketLeg,
    build_bracket,
    round_to_tick,
    to_ib_orders,
)


def test_round_to_tick():
    assert round_to_tick(23.7531) == 23.75
    assert round_to_tick(23.756) == 23.76
    assert round_to_tick(10.0, 0) == 10.0  # tick<=0 ⇒ no rounding


def test_build_bracket_with_take_profit():
    legs = build_bracket(
        qty=100, entry_limit=10.0, stop_price=9.0, take_profit_price=11.0, parent_id=42
    )
    assert len(legs) == 3
    parent, stop, tp = legs
    assert parent == BracketLeg(42, 0, "BUY", 100, "LMT", 10.0, None, False)
    assert stop == BracketLeg(43, 42, "SELL", 100, "STP", None, 9.0, False)
    assert tp == BracketLeg(44, 42, "SELL", 100, "LMT", 11.0, None, True)
    # exactly one transmit=True, and it is the last leg
    assert [leg.transmit for leg in legs] == [False, False, True]


def test_build_bracket_without_take_profit_stop_transmits():
    legs = build_bracket(100, 10.0, 9.0, None, parent_id=1)
    assert len(legs) == 2
    assert legs[0].transmit is False
    assert legs[1].transmit is True  # stop is now the last leg
    assert legs[1].order_type == "STP"


@pytest.mark.parametrize(
    ("qty", "entry", "stop", "tp"),
    [
        (0, 10.0, 9.0, None),  # qty
        (10, 0.0, 9.0, None),  # entry
        (10, 10.0, 10.0, None),  # stop == entry (not below)
        (10, 10.0, 11.0, None),  # stop above entry
        (10, 10.0, 9.0, 10.0),  # tp == entry (not above)
        (10, 10.0, 9.0, 9.5),  # tp below entry
    ],
)
def test_build_bracket_rejects_degenerate(qty, entry, stop, tp):
    with pytest.raises(ValueError):
        build_bracket(qty, entry, stop, tp, parent_id=1)


def test_build_bracket_tick_rounds_prices():
    legs = build_bracket(100, 10.017, 9.012, 11.034, parent_id=1)
    assert legs[0].limit_price == 10.02
    assert legs[1].stop_price == 9.01
    assert legs[2].limit_price == 11.03


def test_to_ib_orders_maps_legs():
    legs = build_bracket(100, 10.0, 9.0, 11.0, parent_id=5)
    orders = to_ib_orders(legs)
    assert len(orders) == 3
    assert [o.orderId for o in orders] == [5, 6, 7]
    assert [o.parentId for o in orders] == [0, 5, 5]
    assert [o.transmit for o in orders] == [False, False, True]
    assert orders[0].action == "BUY" and orders[0].lmtPrice == 10.0
    # ib_async StopOrder stores the stop level in auxPrice.
    assert orders[1].action == "SELL" and orders[1].auxPrice == 9.0
    assert orders[2].action == "SELL" and orders[2].lmtPrice == 11.0
