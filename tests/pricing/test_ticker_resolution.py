"""Tests for ticker resolution persistence (Phase 13) — pure, no DB, no HTTP."""

from __future__ import annotations

from types import SimpleNamespace

from src.pricing.openfigi_resolver import OpenFIGISource, YahooTickerResult
from src.pricing.ticker_resolution import (
    apply_resolution,
    bbg_to_ibkr_exchange,
    ibkr_symbol_from_yahoo,
    is_isin,
    needs_resolution,
    resolve_and_persist,
)


def _deal(**kw):
    base = {
        "id": 1,
        "ticker_target": None,
        "trading_ticker_yf": None,
        "ibkr_ticker": None,
        "ibkr_exchange": None,
        "ticker_resolution_flag": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _result(source, yahoo=None, exch=None):
    return YahooTickerResult(
        isin="FR0000060303", yahoo_ticker=yahoo, exch_code_bbg=exch, figi="X", source=source
    )


def test_is_isin():
    assert is_isin("FR0000060303")
    assert is_isin("DE0006209901")
    assert not is_isin("COVH.PA")
    assert not is_isin(None)
    assert not is_isin("FR000006030")  # too short


def test_bbg_to_ibkr_exchange():
    assert bbg_to_ibkr_exchange("FP") == "SBF"
    assert bbg_to_ibkr_exchange("GR") == "IBIS"
    assert bbg_to_ibkr_exchange("IM") == "BVME"
    assert bbg_to_ibkr_exchange("ZZ") == "SMART"  # unknown
    assert bbg_to_ibkr_exchange(None) == "SMART"


def test_ibkr_symbol_from_yahoo():
    assert ibkr_symbol_from_yahoo("COVH.PA") == "COVH"
    assert ibkr_symbol_from_yahoo("8T6.DE") == "8T6"
    assert ibkr_symbol_from_yahoo("NODOT") == "NODOT"


def test_apply_resolution_home_venue_sets_all():
    deal = _deal()
    flag = apply_resolution(deal, _result(OpenFIGISource.HOME_VENUE, "COVH.PA", "FP"))
    assert flag == "home_venue"
    assert deal.ticker_resolution_flag == "home_venue"
    assert deal.trading_ticker_yf == "COVH.PA"
    assert deal.ibkr_ticker == "COVH"
    assert deal.ibkr_exchange == "SBF"


def test_apply_resolution_growth_flag():
    deal = _deal()
    flag = apply_resolution(deal, _result(OpenFIGISource.HOME_VENUE_GROWTH, "ALXYZ.PA", "XS"))
    assert flag == "home_venue_growth"
    assert deal.trading_ticker_yf == "ALXYZ.PA"
    assert deal.ibkr_exchange == "SBF"


def test_apply_resolution_no_match_leaves_tickers_null():
    deal = _deal()
    flag = apply_resolution(deal, _result(OpenFIGISource.NO_MATCH))
    assert flag == "no_match"
    assert deal.trading_ticker_yf is None
    assert deal.ibkr_ticker is None
    assert deal.ibkr_exchange is None


def test_needs_resolution():
    assert needs_resolution(_deal())
    assert not needs_resolution(_deal(ticker_resolution_flag="home_venue"))
    assert not needs_resolution(_deal(ticker_resolution_flag="no_match"))


class _FakeOpenFIGI:
    def __init__(self, result):
        self._result = result
        self.calls: list[str] = []

    def resolve_isin_to_yahoo_ticker(self, isin):
        self.calls.append(isin)
        return self._result


async def test_resolve_and_persist_with_isin():
    deal = _deal(ticker_target="FR0000060303")
    figi = _FakeOpenFIGI(_result(OpenFIGISource.HOME_VENUE, "COVH.PA", "FP"))
    flag = await resolve_and_persist(deal, figi)
    assert flag == "home_venue"
    assert deal.trading_ticker_yf == "COVH.PA"
    assert figi.calls == ["FR0000060303"]


async def test_resolve_and_persist_without_isin_skips_http():
    deal = _deal(ticker_target=None)
    figi = _FakeOpenFIGI(_result(OpenFIGISource.HOME_VENUE, "X.PA", "FP"))
    flag = await resolve_and_persist(deal, figi)
    assert flag == "not_isin"
    assert deal.trading_ticker_yf is None
    assert figi.calls == []  # no resolution attempted
