"""Integration tests for TradeExecutor — real DB session, faked IBKR."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.core.models import Deal, PaperPosition, Trade
from src.trading.decision_engine import TradeRequest
from src.trading.executor import TradeExecutor

pytestmark = pytest.mark.integration


class FakeIbkr:
    def __init__(self):
        self.placed = []
        self._oid = 1000

    async def qualify_contract(self, symbol, exchange, currency="EUR"):
        return SimpleNamespace(symbol=symbol, conId=1)

    async def qualify_by_isin(self, isin, exchange="SMART", currency="EUR"):
        return SimpleNamespace(isin=isin, conId=2)

    def next_order_id(self):
        self._oid += 10
        return self._oid

    def place_order(self, contract, order):
        self.placed.append(order)


async def _make_deal(session, **kw):
    deal = Deal(
        juridiction=kw.get("juridiction", "DE"),
        regulator_ref=kw.get("regulator_ref", f"REF-{uuid4().hex[:8]}"),
        target_name=kw.get("target_name", "Commerzbank"),
        acquirer_name=kw.get("acquirer_name", "UniCredit"),
        announcement_date=date(2026, 5, 5),
        deal_type="opa",
        status="announced",
    )
    session.add(deal)
    await session.flush()
    return deal


def _req(deal_id, **kw):
    base = {
        "trade_id": str(uuid4()),
        "deal_id": deal_id,
        "deal_target": "Commerzbank",
        "deal_acquirer": "UniCredit",
        "side": "BUY",
        "quantity": 100,
        "symbol": "CBK",
        "exchange": "IBIS",
        "isin": None,
        "currency": "EUR",
        "limit_price": 10.0,
        "stop_loss_price": 9.0,
        "take_profit_price": 11.0,
        "expected_p_completion": 0.95,
        "expected_return_pct": 0.05,
        "kelly_fractional_pct": 0.1,
        "position_pct": 0.1,
        "rationale": "test",
        "requires_approval": False,
    }
    base.update(kw)
    return TradeRequest(**base)


async def test_submit_places_bracket_and_is_idempotent(db_session):
    deal = await _make_deal(db_session)
    ibkr = FakeIbkr()
    ex = TradeExecutor(ibkr)
    req = _req(deal.id)

    trade = await ex.submit(db_session, req)
    assert trade is not None and trade.status == "SUBMITTED"
    assert trade.ibkr_order_id is not None
    assert len(ibkr.placed) == 3  # parent + stop + tp

    # Re-submit same trade_id → no-op, no extra orders.
    again = await ex.submit(db_session, req)
    assert again.status == "SUBMITTED"
    assert len(ibkr.placed) == 3
    rows = (await db_session.scalars(select(Trade).where(Trade.deal_id == deal.id))).all()
    assert len(rows) == 1


async def test_rampup_holds_pending_until_approved(db_session):
    deal = await _make_deal(db_session)
    ibkr = FakeIbkr()
    ex = TradeExecutor(ibkr)
    req = _req(deal.id, requires_approval=True)

    pending = await ex.submit(db_session, req)
    assert pending.status == "PENDING"
    assert ibkr.placed == []  # not sent without approval

    placed = await ex.submit(db_session, req, approved=True)
    assert placed.status == "SUBMITTED"
    assert len(ibkr.placed) == 3


async def test_dedup_skips_second_open_trade_same_deal(db_session):
    deal = await _make_deal(db_session)
    ibkr = FakeIbkr()
    ex = TradeExecutor(ibkr)

    first = await ex.submit(db_session, _req(deal.id))
    assert first.status == "SUBMITTED"

    second = await ex.submit(db_session, _req(deal.id))  # different trade_id, same deal
    assert second is None
    assert len(ibkr.placed) == 3  # second never placed


async def test_reject_when_ticker_unresolved(db_session):
    deal = await _make_deal(db_session)
    ex = TradeExecutor(FakeIbkr())
    req = _req(deal.id, symbol=None, exchange=None, isin=None)
    trade = await ex.submit(db_session, req)
    assert trade is not None and trade.status == "REJECTED"
    assert trade.rejection_reason == "ticker_unresolved"


async def test_mark_filled_opens_paper_position(db_session):
    deal = await _make_deal(db_session)
    ex = TradeExecutor(FakeIbkr())
    trade = await ex.submit(db_session, _req(deal.id))
    await ex.mark_filled(db_session, trade, filled_price=10.0, filled_quantity=100)

    assert trade.status == "FILLED"
    pos = await db_session.scalar(select(PaperPosition).where(PaperPosition.deal_id == deal.id))
    assert pos is not None
    assert pos.status == "open"
    assert float(pos.entry_price) == pytest.approx(10.0)
    assert float(pos.size_eur) == pytest.approx(1000.0)


async def test_buy_fills_average_entry(db_session):
    deal = await _make_deal(db_session)
    ex = TradeExecutor(FakeIbkr())
    t1 = await ex.submit(db_session, _req(deal.id))
    # two tranches on the same open position
    await ex.mark_filled(db_session, t1, 10.0, 100)  # 1000 EUR @ 10
    await ex.mark_filled(db_session, t1, 12.0, 100)  # +1200 EUR @ 12

    pos = await db_session.scalar(select(PaperPosition).where(PaperPosition.deal_id == deal.id))
    assert float(pos.size_eur) == pytest.approx(2200.0)
    # weighted-by-euro entry between 10 and 12
    assert 10.0 < float(pos.entry_price) < 12.0


async def test_sell_closes_position_with_pnl(db_session):
    deal = await _make_deal(db_session)
    ex = TradeExecutor(FakeIbkr())
    buy = await ex.submit(db_session, _req(deal.id))
    await ex.mark_filled(db_session, buy, 10.0, 100)

    sell = Trade(
        trade_id=str(uuid4()),
        deal_id=deal.id,
        side="SELL",
        quantity=100,
        status="SUBMITTED",
    )
    db_session.add(sell)
    await db_session.flush()
    await ex.mark_filled(db_session, sell, 11.0, 100)

    pos = await db_session.scalar(select(PaperPosition).where(PaperPosition.deal_id == deal.id))
    assert pos.status == "closed"
    assert float(pos.exit_price) == pytest.approx(11.0)
    assert float(pos.pnl_eur) == pytest.approx(100.0)  # (11/10 - 1) * 1000
