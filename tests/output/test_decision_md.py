"""Tests for the decision MD surface (Phase 13) — pure, no DB, no broker."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from src.output.decision_md import (
    decision_filename,
    render_decision_md,
    update_decision_index,
    write_decision_md,
)
from src.trading.decision_engine import TradeRequest

TODAY = date(2026, 6, 3)


def _req(**kw) -> TradeRequest:
    base = {
        "trade_id": "t1",
        "deal_id": 7,
        "deal_target": "Covivio Hotels",
        "deal_acquirer": "Covivio SA",
        "side": "BUY",
        "quantity": 120,
        "symbol": "COVH",
        "exchange": "SBF",
        "isin": "FR0000060303",
        "currency": "EUR",
        "limit_price": 50.05,
        "stop_loss_price": 45.05,
        "take_profit_price": 52.0,
        "expected_p_completion": 0.92,
        "expected_return_pct": 0.039,
        "kelly_fractional_pct": 0.08,
        "position_pct": 0.06,
        "rationale": "r",
        "requires_approval": False,
        "score_stars": 4,
    }
    base.update(kw)
    return TradeRequest(**base)


def _deal(**kw):
    base = {
        "target_name": "Covivio Hotels",
        "juridiction": "FR",
        "ticker_target": "FR0000060303",
        "trading_ticker_yf": "COVH.PA",
        "ibkr_ticker": "COVH",
        "ibkr_exchange": "SBF",
        "offer_price": Decimal("52.0"),
        "reference_price_at_announcement": Decimal("50.0"),
        "premium_pct": Decimal("0.0400"),
        "deal_type": "opa",
        "payment_cash_share": Decimal("1.0"),
        "regulator_ref": "224C0763",
        "source_url": "https://amf-france.org/224C0763",
        "announcement_date": date(2026, 5, 20),
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_render_has_all_critical_fields():
    md = render_decision_md(_req(), _deal(), today=TODAY)
    assert "# Décision — Covivio Hotels" in md
    # Both tickers present, clearly labelled.
    assert "Ticker (yfinance) : COVH.PA" in md
    assert "Ticker (IBKR) : COVH @ SBF" in md
    # Order block.
    assert "Entry : 50.05 EUR" in md
    assert "Stop : 45.05 EUR" in md
    assert "Take-profit : 52.00 EUR" in md
    assert "120 actions" in md and "6.0% du capital" in md
    # Strategy + rationale.
    assert "Merger arb" in md
    assert "Score complétion : 4/5" in md
    assert "Premium offre : 4.0%" in md
    assert "Spread actuel : 3.9%" in md
    # Source.
    assert "224C0763" in md
    assert "https://amf-france.org/224C0763" in md


def test_render_premium_null_renders_na_no_crash():
    deal = _deal(premium_pct=None, reference_price_at_announcement=None, offer_price=None)
    md = render_decision_md(_req(), deal, today=TODAY)
    assert "Premium offre : N/A" in md  # no crash, graceful N/A


def test_render_no_ibkr_ticker_falls_back_to_isin():
    deal = _deal(ibkr_ticker=None, ibkr_exchange=None)
    md = render_decision_md(_req(symbol=None, exchange=None), deal, today=TODAY)
    assert "Ticker (IBKR) : via ISIN FR0000060303" in md


def test_decision_filename():
    assert decision_filename(_deal(), TODAY) == "2026-06-03_FR0000060303_covivio-hotels.md"


def test_write_and_index_roundtrip(tmp_path):
    path = write_decision_md(_req(), _deal(), decisions_dir=tmp_path, today=TODAY)
    assert path.exists()
    assert path.name == "2026-06-03_FR0000060303_covivio-hotels.md"

    update_decision_index(_req(), _deal(), path, decisions_dir=tmp_path, today=TODAY)
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "| Date | Cible | Jur. | Ticker IBKR |" in index
    assert "Covivio Hotels" in index and "COVH" in index
    assert "[2026-06-03_FR0000060303_covivio-hotels.md]" in index


def test_index_upsert_sorted_desc(tmp_path):
    # Older decision first, then a newer one — newest must end up on top.
    old = _deal(target_name="Old Deal", ticker_target="FR0000000001")
    new = _deal(target_name="New Deal", ticker_target="FR0000000002")
    req_old = _req(deal_id=1, deal_target="Old Deal")
    req_new = _req(deal_id=2, deal_target="New Deal")
    p_old = write_decision_md(req_old, old, decisions_dir=tmp_path, today=date(2026, 6, 1))
    update_decision_index(req_old, old, p_old, decisions_dir=tmp_path, today=date(2026, 6, 1))
    p_new = write_decision_md(req_new, new, decisions_dir=tmp_path, today=date(2026, 6, 3))
    update_decision_index(req_new, new, p_new, decisions_dir=tmp_path, today=date(2026, 6, 3))
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert index.index("New Deal") < index.index("Old Deal")  # newest on top
    # Idempotent upsert: re-emitting the new one keeps a single row.
    update_decision_index(req_new, new, p_new, decisions_dir=tmp_path, today=date(2026, 6, 3))
    index2 = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert index2.count("New Deal") == 1
