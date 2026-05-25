"""Unit tests for Kelly-fractional position sizing (pure)."""

from __future__ import annotations

import pytest

from src.trading.position_sizing import (
    CAPITAL_CAP,
    CAPITAL_FLOOR,
    MAX_POSITION_PCT,
    PositionSizer,
    compute_kelly,
    effective_capital,
)


# --------------------------------------------------------- effective capital
@pytest.mark.parametrize(
    ("net_liq", "expected"),
    [
        (1_000_000, 1_000_000),  # in band
        (5_000_000, CAPITAL_CAP),  # above cap
        (10_000, CAPITAL_FLOOR),  # below floor
    ],
)
def test_effective_capital_clamp(net_liq, expected):
    assert effective_capital(net_liq) == expected


# ------------------------------------------------------------------- kelly
def test_compute_kelly_full_edge():
    # p=1, er=5% ⇒ full Kelly 1.0, fractional 0.15, capped at 0.12.
    raw, frac, pct = compute_kelly(1.0, 0.05)
    assert raw == pytest.approx(1.0)
    assert frac == pytest.approx(0.15)
    assert pct == MAX_POSITION_PCT


def test_compute_kelly_partial_edge():
    raw, frac, pct = compute_kelly(0.9, 0.05)
    assert raw == pytest.approx(0.6)
    assert frac == pytest.approx(0.09)
    assert pct == pytest.approx(0.09)


def test_compute_kelly_negative_edge_zeroes():
    # p=0.5 with 5% spread but 15% break loss ⇒ negative Kelly ⇒ 0.
    assert compute_kelly(0.5, 0.05) == (pytest.approx(-1.0), pytest.approx(-0.15), 0.0)


def test_compute_kelly_no_spread():
    assert compute_kelly(0.99, 0.0) == (0.0, 0.0, 0.0)
    assert compute_kelly(0.99, -0.02) == (0.0, 0.0, 0.0)


# ------------------------------------------------------------------- sizing
def test_size_happy_path():
    r = PositionSizer().size(
        p_completion=1.0, expected_return=0.05, entry_price=10.0, net_liquidation=1_000_000
    )
    assert r.tradeable
    assert r.position_pct == MAX_POSITION_PCT
    assert r.size_qty == 12_000  # 0.12 * 1M / 10
    assert r.size_eur == pytest.approx(120_000)


def test_size_no_edge_returns_zero_qty():
    r = PositionSizer().size(0.5, 0.05, 10.0, 1_000_000)
    assert not r.tradeable
    assert r.reason == "no_edge"
    assert r.size_qty == 0


def test_size_position_cap():
    r = PositionSizer().size(1.0, 0.05, 10.0, 1_000_000, open_positions=5)
    assert r.reason == "position_cap"
    assert not r.tradeable


def test_size_bad_price():
    r = PositionSizer().size(1.0, 0.05, 0.0, 1_000_000)
    assert r.reason == "bad_price"


def test_size_below_min_on_small_capital_and_thin_edge():
    # Thin edge (p≈0.76) on the floor capital ⇒ < €1000 ⇒ below_min.
    r = PositionSizer().size(0.76, 0.05, 10.0, 10_000)
    assert r.reason == "below_min"
    assert r.size_qty == 0


def test_size_quantity_floors_down():
    r = PositionSizer().size(1.0, 0.05, 10_000.0, 1_000_000)
    # 0.12*1M = 120k budget / 10k price = 12 shares exactly.
    assert r.size_qty == 12
    assert r.size_eur == pytest.approx(120_000)


def test_size_uses_clamped_capital():
    # 5M net liq clamps to 2M cap ⇒ 0.12*2M = 240k.
    r = PositionSizer().size(1.0, 0.05, 10.0, 5_000_000)
    assert r.effective_capital == CAPITAL_CAP
    assert r.size_qty == 24_000
