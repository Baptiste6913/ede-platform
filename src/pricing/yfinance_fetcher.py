"""yfinance EOD-close lookup with a local SQLite cache (Phase 9.1c).

Public API: :func:`get_close_eur` returns the closing price of ``ticker``,
converted to EUR if needed, on the latest trading day on or before
``target_date`` (within ``max_lookback_days``). Returns ``None`` on a miss; no
"best-effort" estimation when an FX rate is unavailable.

Cache: ``data/cache/yfinance.db`` (gitignored), TTL 30 days. The module-level
``CACHE_PATH``, ``CACHE_TTL`` and ``RETRY_BACKOFFS`` are intentionally module
attributes (not ``Final``) so tests can monkeypatch them.

Retries: 3 attempts on exception with backoff 1 s / 3 s / 9 s; an empty result
(no data in window) is not retried.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import structlog
import yfinance as yf

log = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

CACHE_PATH: Path = _REPO_ROOT / "data" / "cache" / "yfinance.db"
CACHE_TTL: timedelta = timedelta(days=30)
RETRY_BACKOFFS: tuple[float, ...] = (1.0, 3.0, 9.0)


def _connect() -> sqlite3.Connection:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS yfinance_close ("
        "  ticker TEXT NOT NULL,"
        "  target_date TEXT NOT NULL,"
        "  actual_date TEXT NOT NULL,"
        "  close_eur TEXT NOT NULL,"
        "  currency_orig TEXT NOT NULL,"
        "  fetched_at TEXT NOT NULL,"
        "  PRIMARY KEY (ticker, target_date)"
        ")"
    )
    conn.commit()
    return conn


def _cache_get(
    conn: sqlite3.Connection, ticker: str, target_date: date
) -> tuple[Decimal, date] | None:
    row = conn.execute(
        "SELECT actual_date, close_eur, fetched_at FROM yfinance_close "
        "WHERE ticker = ? AND target_date = ?",
        (ticker, target_date.isoformat()),
    ).fetchone()
    if row is None:
        return None
    actual_iso, close_eur_str, fetched_at_iso = row
    if datetime.now(tz=UTC) - datetime.fromisoformat(fetched_at_iso) > CACHE_TTL:
        return None  # expired
    return (Decimal(close_eur_str), date.fromisoformat(actual_iso))


def _cache_put(
    conn: sqlite3.Connection,
    ticker: str,
    target_date: date,
    actual_date: date,
    close_eur: Decimal,
    currency_orig: str,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO yfinance_close "
        "(ticker, target_date, actual_date, close_eur, currency_orig, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            ticker,
            target_date.isoformat(),
            actual_date.isoformat(),
            str(close_eur),
            currency_orig,
            datetime.now(tz=UTC).isoformat(),
        ),
    )
    conn.commit()


def _fetch_close_with_lookback(
    ticker: str, target_date: date, max_lookback_days: int
) -> tuple[Decimal, date, str] | None:
    """Latest Close <= target_date in [target - lookback, target]; retries on
    exception with the configured backoff. Returns (close, actual_date,
    currency_orig) or None."""
    start = target_date - timedelta(days=max_lookback_days)
    end = target_date + timedelta(days=1)  # yfinance end is exclusive
    last_err: Exception | None = None
    attempts = 1 + len(RETRY_BACKOFFS)
    for attempt in range(attempts):
        if attempt > 0:
            time.sleep(RETRY_BACKOFFS[attempt - 1])
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(start=start, end=end)
            if hist is None or hist.empty or "Close" not in hist:
                return None  # no data within window — not transient, don't retry
            closes = hist["Close"].dropna()
            if closes.empty:
                return None
            last_idx = closes.index[-1]
            actual = last_idx.date() if hasattr(last_idx, "date") else last_idx
            if isinstance(actual, datetime):
                actual = actual.date()
            close = Decimal(str(round(float(closes.iloc[-1]), 6)))
            currency = "EUR"
            try:
                currency = str(tk.fast_info.get("currency") or "EUR")
            except Exception:
                currency = "EUR"
            return (close, actual, currency)
        except Exception as exc:
            last_err = exc
            log.debug(
                "yfinance.fetch_attempt_failed", ticker=ticker, attempt=attempt, error=str(exc)
            )
    log.warning(
        "yfinance.fetch_failed",
        ticker=ticker,
        target_date=str(target_date),
        attempts=attempts,
        error=str(last_err) if last_err else "",
    )
    return None


def _fx_to_eur(conn: sqlite3.Connection, currency_orig: str, actual_date: date) -> Decimal | None:
    """Conversion factor: a price in ``currency_orig`` becomes EUR by *dividing*
    by this factor (``EUR<cur>=X`` = how many <cur> per 1 EUR). FX is cached
    in the same SQLite table under its own ticker; missing FX yields None."""
    if currency_orig == "EUR":
        return Decimal("1")
    fx_ticker = f"EUR{currency_orig}=X"
    cached = _cache_get(conn, fx_ticker, actual_date)
    if cached is not None:
        return cached[0]
    fetched = _fetch_close_with_lookback(fx_ticker, actual_date, max_lookback_days=5)
    if fetched is None:
        return None
    rate, eff_date, _ = fetched
    _cache_put(conn, fx_ticker, actual_date, eff_date, rate, currency_orig)
    return rate


def get_close_eur(
    ticker: str,
    target_date: date,
    *,
    max_lookback_days: int = 5,
) -> tuple[Decimal, date] | None:
    """Return ``(close_in_eur, effective_trading_date)`` or ``None`` on miss.

    Falls back up to ``max_lookback_days`` trading days when ``target_date``
    is a weekend/holiday. Non-EUR closes are converted via the ``EUR<cur>=X``
    rate on the SAME effective date; if the FX rate is unavailable, returns
    ``None`` (no estimation). Cached locally for 30 days.
    """
    conn = _connect()
    try:
        cached = _cache_get(conn, ticker, target_date)
        if cached is not None:
            return cached

        fetched = _fetch_close_with_lookback(ticker, target_date, max_lookback_days)
        if fetched is None:
            return None
        close_orig, actual_date, currency = fetched
        if currency == "EUR":
            close_eur = close_orig
        else:
            fx_rate = _fx_to_eur(conn, currency, actual_date)
            if fx_rate is None:
                log.warning(
                    "yfinance.fx_miss",
                    ticker=ticker,
                    currency=currency,
                    date=str(actual_date),
                )
                return None
            close_eur = (close_orig / fx_rate).quantize(Decimal("0.000001"))

        _cache_put(conn, ticker, target_date, actual_date, close_eur, currency)
        return (close_eur, actual_date)
    finally:
        conn.close()
