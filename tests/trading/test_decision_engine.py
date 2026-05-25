"""Unit tests for the decision engine (pure — injected sizer, no IBKR/DB)."""

from __future__ import annotations

import pytest

from src.trading.decision_engine import (
    DealCandidate,
    DecisionEngine,
    TradingConfig,
    compute_spread,
    entry_limit_price,
    evaluate_candidate,
    reference_price,
)
from src.trading.ibkr_client import PriceSnapshot
from src.trading.position_sizing import PositionSizer

CFG = TradingConfig()
SIZER = PositionSizer()


def _snap(*, bid=None, ask=None, last=None, close=None):
    return PriceSnapshot(bid=bid, ask=ask, last=last, close=close, market_data_type=3)


def _candidate(**kw):
    base = {
        "deal_id": 1,
        "target_name": "Commerzbank",
        "acquirer_name": "UniCredit",
        "juridiction": "DE",
        "offer_price": 180.0,
        "p_completion": 0.95,
        "score_stars": 5,
        "symbol": "CBK",
        "exchange": "IBIS",
        "isin": None,
    }
    base.update(kw)
    return DealCandidate(**base)


# ----------------------------------------------------------- pure helpers
def test_reference_price_quoted_uses_mid():
    assert reference_price(_snap(bid=166.82, ask=166.94, last=170.0), "DE") == pytest.approx(166.88)


def test_reference_price_it_uses_last():
    # IT: no bid/ask → mid None; engine uses last even if a mid existed.
    assert reference_price(_snap(bid=10.0, ask=10.2, last=9.7), "IT") == 9.7
    assert reference_price(_snap(last=9.765), "IT") == 9.765


def test_entry_limit_offsets():
    assert entry_limit_price(100.0, "DE", CFG) == pytest.approx(100.1)  # +0.1%
    assert entry_limit_price(100.0, "IT", CFG) == pytest.approx(100.4)  # +0.4%


def test_compute_spread():
    assert compute_spread(180.0, 166.88) == pytest.approx((180 - 166.88) / 166.88)


# ------------------------------------------------------------- happy path
def test_evaluate_candidate_builds_request():
    snap = _snap(bid=166.82, ask=166.94)
    req = evaluate_candidate(_candidate(), snap, 1_000_000, 0, 0, SIZER, CFG)
    assert req is not None
    assert req.side == "BUY"
    assert req.deal_id == 1
    assert req.symbol == "CBK"
    assert req.quantity > 0
    assert req.limit_price == pytest.approx(166.88 * 1.001, rel=1e-4)
    assert req.stop_loss_price == pytest.approx(req.limit_price * 0.90, rel=1e-4)
    assert req.take_profit_price == 180.0
    assert req.requires_approval is True  # rampup 0 < 5
    assert req.trade_id  # uuid present
    assert "merger-arb" in req.rationale


def test_requires_approval_false_after_rampup():
    snap = _snap(bid=166.82, ask=166.94)
    req = evaluate_candidate(_candidate(), snap, 1_000_000, 0, 5, SIZER, CFG)
    assert req is not None and req.requires_approval is False


# ----------------------------------------------------------------- skips
def test_skip_below_min_score():
    assert (
        evaluate_candidate(_candidate(score_stars=2), _snap(bid=1, ask=1.1), 1e6, 0, 0, SIZER, CFG)
        is None
    )


def test_skip_no_offer_price():
    assert (
        evaluate_candidate(
            _candidate(offer_price=None), _snap(bid=1, ask=1.1), 1e6, 0, 0, SIZER, CFG
        )
        is None
    )


def test_skip_no_price():
    assert evaluate_candidate(_candidate(), _snap(), 1e6, 0, 0, SIZER, CFG) is None


def test_skip_thin_spread():
    # offer barely above reference → spread < 1% → skip.
    snap = _snap(bid=179.0, ask=179.2)  # mid 179.1, offer 180 → spread 0.5%
    assert evaluate_candidate(_candidate(), snap, 1e6, 0, 0, SIZER, CFG) is None


def test_skip_when_position_cap_reached():
    snap = _snap(bid=166.82, ask=166.94)
    assert evaluate_candidate(_candidate(), snap, 1e6, 5, 0, SIZER, CFG) is None


def test_skip_when_no_edge_negative_kelly():
    # Low p_completion → negative Kelly → sizing not tradeable → skip.
    snap = _snap(bid=166.82, ask=166.94)
    assert evaluate_candidate(_candidate(p_completion=0.5), snap, 1e6, 0, 0, SIZER, CFG) is None


# --------------------------------------------------------- engine wrapper
def test_decision_engine_evaluate():
    engine = DecisionEngine()
    req = engine.evaluate(_candidate(), _snap(bid=166.82, ask=166.94), 1_000_000, 0, 0)
    assert req is not None and req.quantity > 0
