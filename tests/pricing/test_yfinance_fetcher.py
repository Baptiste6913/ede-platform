"""Unit tests for :mod:`src.pricing.yfinance_fetcher`.

`yfinance` 1.4 uses curl_cffi (which vcrpy does not intercept), so the HTTP
layer is mocked directly: a :class:`FakeTicker` returns pre-built pandas frames
and yields the same currency / history surface as :class:`yfinance.Ticker`.
Each test uses an isolated SQLite cache under ``tmp_path``.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from src.pricing import yfinance_fetcher as fetcher


class FakeTicker:
    """yf.Ticker stand-in. Each call to ``history()`` consumes one entry from
    ``raises_then`` — an exception (raised) or ``None`` (return the frame)."""

    def __init__(
        self,
        history_df: pd.DataFrame | None = None,
        raises_then: list[Exception | None] | None = None,
        currency: str = "EUR",
    ) -> None:
        self.history_df = history_df if history_df is not None else pd.DataFrame()
        self.raises_then = list(raises_then) if raises_then else []
        self.currency = currency
        self.history_calls = 0

    def history(self, start: date, end: date) -> pd.DataFrame:
        self.history_calls += 1
        if self.raises_then:
            action = self.raises_then.pop(0)
            if action is not None:
                raise action
        df = self.history_df
        if df.empty:
            return df
        mask = (df.index >= pd.Timestamp(start)) & (df.index < pd.Timestamp(end))
        return df.loc[mask]

    @property
    def fast_info(self) -> dict[str, str]:
        return {"currency": self.currency}


def _frame(closes: dict[date, float]) -> pd.DataFrame:
    if not closes:
        return pd.DataFrame()
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in closes])
    return pd.DataFrame({"Close": list(closes.values())}, index=idx)


@pytest.fixture
def mock_yf(monkeypatch, tmp_path):
    """Isolate cache + skip retry sleeps + route yf.Ticker(symbol) to a registry."""
    monkeypatch.setattr(fetcher, "CACHE_PATH", tmp_path / "yfinance.db")
    monkeypatch.setattr("time.sleep", lambda _s: None)

    tickers: dict[str, FakeTicker] = {}

    def _factory(symbol: str) -> FakeTicker:
        if symbol not in tickers:
            raise AssertionError(f"unexpected ticker request: {symbol!r}")
        return tickers[symbol]

    monkeypatch.setattr(fetcher.yf, "Ticker", _factory)
    return tickers


# --------------------------------------------------------------- happy paths


def test_eur_native_ticker(mock_yf):
    mock_yf["UCG.MI"] = FakeTicker(_frame({date(2026, 5, 25): 74.09}), currency="EUR")
    result = fetcher.get_close_eur("UCG.MI", date(2026, 5, 25))
    assert result == (Decimal("74.090000"), date(2026, 5, 25))
    assert mock_yf["UCG.MI"].history_calls == 1


def test_non_trading_day_fallback(mock_yf):
    # Target = Saturday 2026-05-23; latest trading close = Friday 2026-05-22.
    mock_yf["UCG.MI"] = FakeTicker(_frame({date(2026, 5, 22): 73.10}), currency="EUR")
    price, actual = fetcher.get_close_eur("UCG.MI", date(2026, 5, 23))  # type: ignore[misc]
    assert price == Decimal("73.100000")
    assert actual == date(2026, 5, 22)


def test_extended_holiday_fallback(mock_yf):
    # Target = Thu 2025-12-25 (Christmas) — fall back to Tue 2025-12-23.
    mock_yf["FOO.DE"] = FakeTicker(_frame({date(2025, 12, 23): 42.0}), currency="EUR")
    price, actual = fetcher.get_close_eur("FOO.DE", date(2025, 12, 25))  # type: ignore[misc]
    assert price == Decimal("42.000000")
    assert actual == date(2025, 12, 23)


# ------------------------------------------------------------------ misses


def test_max_lookback_exceeded_returns_none(mock_yf):
    # No data within the 5-day window (e.g. pre-IPO).
    mock_yf["NEW.DE"] = FakeTicker(_frame({}), currency="EUR")
    assert fetcher.get_close_eur("NEW.DE", date(2026, 5, 25)) is None


# ------------------------------------------------------------------- cache


def test_cache_hit_skips_network(mock_yf):
    mock_yf["UCG.MI"] = FakeTicker(_frame({date(2026, 5, 25): 74.09}), currency="EUR")
    first = fetcher.get_close_eur("UCG.MI", date(2026, 5, 25))
    second = fetcher.get_close_eur("UCG.MI", date(2026, 5, 25))
    assert first == second
    assert mock_yf["UCG.MI"].history_calls == 1  # second call served from cache


def test_cache_expiry_refetches(mock_yf):
    mock_yf["UCG.MI"] = FakeTicker(_frame({date(2026, 5, 25): 74.09}), currency="EUR")
    # First call populates the cache (schema + row).
    fetcher.get_close_eur("UCG.MI", date(2026, 5, 25))
    assert mock_yf["UCG.MI"].history_calls == 1
    # Backdate the cached row beyond TTL.
    stale = (datetime.now(tz=UTC) - fetcher.CACHE_TTL - timedelta(days=1)).isoformat()
    conn = sqlite3.connect(fetcher.CACHE_PATH)
    conn.execute(
        "UPDATE yfinance_close SET fetched_at = ? WHERE ticker = ?",
        (stale, "UCG.MI"),
    )
    conn.commit()
    conn.close()
    # Second call should re-fetch because the cached row is expired.
    fetcher.get_close_eur("UCG.MI", date(2026, 5, 25))
    assert mock_yf["UCG.MI"].history_calls == 2


# ----------------------------------------------------------------- FX path


def test_fx_conversion_usd_to_eur(mock_yf):
    # AAPL = 150 USD on 2026-05-25; EURUSD = 1.08 USD per EUR ⇒ 138.888889 EUR.
    mock_yf["AAPL"] = FakeTicker(_frame({date(2026, 5, 25): 150.0}), currency="USD")
    mock_yf["EURUSD=X"] = FakeTicker(_frame({date(2026, 5, 25): 1.08}), currency="USD")
    price, actual = fetcher.get_close_eur("AAPL", date(2026, 5, 25))  # type: ignore[misc]
    assert actual == date(2026, 5, 25)
    assert price == Decimal("138.888889")


def test_fx_miss_returns_none(mock_yf):
    mock_yf["AAPL"] = FakeTicker(_frame({date(2026, 5, 25): 150.0}), currency="USD")
    mock_yf["EURUSD=X"] = FakeTicker(_frame({}), currency="USD")  # no FX data
    assert fetcher.get_close_eur("AAPL", date(2026, 5, 25)) is None


# ---------------------------------------------------------------- retries


def test_retry_succeeds_after_transient_exceptions(mock_yf):
    mock_yf["UCG.MI"] = FakeTicker(
        _frame({date(2026, 5, 25): 74.09}),
        raises_then=[RuntimeError("rate limited"), RuntimeError("rate limited"), None],
        currency="EUR",
    )
    result = fetcher.get_close_eur("UCG.MI", date(2026, 5, 25))
    assert result == (Decimal("74.090000"), date(2026, 5, 25))
    assert mock_yf["UCG.MI"].history_calls == 3  # 2 failures + 1 success


def test_retry_exhausted_returns_none(mock_yf):
    mock_yf["UCG.MI"] = FakeTicker(
        _frame({date(2026, 5, 25): 74.09}),
        raises_then=[RuntimeError("boom")] * 4,  # all 4 attempts fail
        currency="EUR",
    )
    assert fetcher.get_close_eur("UCG.MI", date(2026, 5, 25)) is None
    assert mock_yf["UCG.MI"].history_calls == 4
