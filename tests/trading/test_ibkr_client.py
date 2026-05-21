"""Unit tests for IbkrClient — fake ib_async, no network/Gateway."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from src.trading.ibkr_client import (
    DELAYED_MARKET_DATA,
    AccountSnapshot,
    IbkrClient,
    PriceSnapshot,
)


# --------------------------------------------------------------------- fakes
class _Event:
    def __iadd__(self, handler):
        return self


class FakeIB:
    """Minimal stand-in for ib_async.IB covering the methods IbkrClient uses."""

    def __init__(
        self,
        *,
        qualify=None,
        tickers=None,
        account_rows=None,
        positions=None,
        connected=True,
    ):
        self.disconnectedEvent = _Event()
        self._connected = connected
        self.market_data_type = None
        self.connect_args = None
        self.placed = []
        self._qualify = qualify
        self._tickers = tickers or []
        self._account_rows = account_rows or []
        self._positions = positions or []

    async def connectAsync(self, host, port, clientId, timeout=None):
        self.connect_args = (host, port, clientId)

    def reqMarketDataType(self, t):
        self.market_data_type = t

    def isConnected(self):
        return self._connected

    def disconnect(self):
        self._connected = False

    async def qualifyContractsAsync(self, contract):
        if self._qualify is not None:
            self._qualify(contract)
        return [contract]

    async def reqTickersAsync(self, contract):
        return self._tickers

    async def accountSummaryAsync(self):
        return self._account_rows

    async def reqPositionsAsync(self):
        return self._positions

    def placeOrder(self, contract, order):
        self.placed.append((contract, order))
        return SimpleNamespace(contract=contract, order=order)


def _settings(*, paper=True, port=7497):
    return SimpleNamespace(
        ibkr_host="127.0.0.1", ibkr_port=port, ibkr_client_id=42, ibkr_paper=paper
    )


def _row(account, tag, value, currency="EUR"):
    return SimpleNamespace(account=account, tag=tag, value=value, currency=currency)


# ---------------------------------------------------------------- paper guard
@pytest.mark.parametrize(
    ("paper", "port"),
    [(False, 7497), (True, 7496), (True, 4001)],
)
async def test_paper_guard_blocks_non_paper(paper, port):
    client = IbkrClient(settings=_settings(paper=paper, port=port), ib=FakeIB())
    with pytest.raises(RuntimeError, match="paper guard"):
        await client.connect()


async def test_connect_sets_state_and_delayed_market_data():
    ib = FakeIB()
    client = IbkrClient(settings=_settings(), ib=ib)
    await client.connect()
    assert client.is_connected
    assert ib.connect_args == ("127.0.0.1", 7497, 42)
    assert ib.market_data_type == DELAYED_MARKET_DATA


async def test_disconnect_resets_state():
    ib = FakeIB()
    client = IbkrClient(settings=_settings(), ib=ib)
    await client.connect()
    await client.disconnect()
    assert client.is_connected is False


# ----------------------------------------------------------------- qualify
async def test_qualify_contract_returns_when_conid_populated():
    def _set_conid(contract):
        contract.conId = 12345

    client = IbkrClient(settings=_settings(), ib=FakeIB(qualify=_set_conid))
    contract = await client.qualify_contract("AIR", "SBF")
    assert contract is not None
    assert contract.conId == 12345


async def test_qualify_contract_returns_none_when_unresolved():
    client = IbkrClient(settings=_settings(), ib=FakeIB(qualify=None))
    # Sanofi/SAN style: no security definition on either routing → None.
    assert await client.qualify_contract("SAN", "SBF") is None


# -------------------------------------------------------------- market data
async def test_get_current_price_drops_minus_one_and_nan():
    # Borsa Italiana delayed: bid/ask = -1 (unavailable), last/close present.
    tk = SimpleNamespace(bid=-1, ask=-1, last=9.765, close=9.669, marketDataType=3)
    client = IbkrClient(settings=_settings(), ib=FakeIB(tickers=[tk]))
    snap = await client.get_current_price(object())
    assert snap.bid is None and snap.ask is None
    assert snap.last == 9.765
    assert snap.mid is None
    assert snap.has_quote is True


async def test_get_current_price_computes_mid_when_quoted():
    tk = SimpleNamespace(bid=166.82, ask=166.94, last=166.94, close=173.36, marketDataType=3)
    client = IbkrClient(settings=_settings(), ib=FakeIB(tickers=[tk]))
    snap = await client.get_current_price(object())
    assert snap.mid == pytest.approx(166.88)


async def test_get_current_price_all_nan_has_no_quote():
    nan = float("nan")
    tk = SimpleNamespace(bid=nan, ask=nan, last=nan, close=nan, marketDataType=1)
    client = IbkrClient(settings=_settings(), ib=FakeIB(tickers=[tk]))
    snap = await client.get_current_price(object())
    assert snap.has_quote is False


# ------------------------------------------------------------------ account
async def test_get_account_summary_picks_du_account():
    rows = [
        _row("All", "NetLiquidation", "0"),
        _row("DUP401220", "NetLiquidation", "1002754.69"),
        _row("DUP401220", "TotalCashValue", "1002031.14"),
    ]
    client = IbkrClient(settings=_settings(), ib=FakeIB(account_rows=rows))
    summary = await client.get_account_summary()
    assert isinstance(summary, AccountSnapshot)
    assert summary.account_id == "DUP401220"
    assert summary.net_liquidation == pytest.approx(1002754.69)
    assert summary.total_cash == pytest.approx(1002031.14)
    assert summary.currency == "EUR"


async def test_get_account_summary_raises_without_du_account():
    rows = [_row("All", "NetLiquidation", "0")]
    client = IbkrClient(settings=_settings(), ib=FakeIB(account_rows=rows))
    with pytest.raises(RuntimeError, match="paper account"):
        await client.get_account_summary()


async def test_get_net_liquidation():
    rows = [_row("DU1", "NetLiquidation", "500000"), _row("DU1", "TotalCashValue", "400000")]
    client = IbkrClient(settings=_settings(), ib=FakeIB(account_rows=rows))
    assert await client.get_net_liquidation() == pytest.approx(500000.0)


# ---------------------------------------------------------------- positions
async def test_get_positions_maps_to_dataclass():
    pos = SimpleNamespace(
        contract=SimpleNamespace(symbol="ENI", exchange="BVME", primaryExchange="BVME"),
        position=100.0,
        avgCost=23.5,
        account="DU1",
    )
    client = IbkrClient(settings=_settings(), ib=FakeIB(positions=[pos]))
    out = await client.get_positions()
    assert len(out) == 1
    assert out[0].symbol == "ENI"
    assert out[0].quantity == 100.0
    assert out[0].avg_cost == 23.5


# ------------------------------------------------------------------- orders
async def test_place_order_delegates_to_ib():
    ib = FakeIB()
    client = IbkrClient(settings=_settings(), ib=ib)
    contract, order = object(), object()
    client.place_order(contract, order)
    assert ib.placed == [(contract, order)]


# --------------------------------------------------------- pure dataclass
def test_price_snapshot_mid_and_has_quote():
    assert PriceSnapshot(10.0, 12.0, 11.0, 9.0, 3).mid == 11.0
    assert PriceSnapshot(None, None, 11.0, 9.0, 3).mid is None
    assert PriceSnapshot(None, None, None, None, 3).has_quote is False
    assert not math.isnan(0.0)  # sanity: helper import used
