"""P9.1c live yfinance probe — 1 live fetch + 1 cache-hit (read-only).

Validates yfinance install + network + the fetcher module end-to-end before
running the full recalc. Targets UCG.MI (the Commerzbank acquirer) one business
day before the Commerzbank announcement (deal 348, 2026-05-05). Prints close
EUR, effective trading day, and latencies; a second call should return the
same value from the SQLite cache instantly.

Run:
  .venv/Scripts/python.exe scripts/probe_yfinance_live.py
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pricing.yfinance_fetcher import CACHE_PATH, get_close_eur

ANNOUNCEMENT = date(2026, 5, 5)  # Commerzbank deal 348
TICKER = "UCG.MI"  # UniCredit (acquirer)


def _prev_business_day(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    return d


def main() -> None:
    target = _prev_business_day(ANNOUNCEMENT)
    print(f"ticker        : {TICKER}")
    print(f"target_date   : {target} (announcement {ANNOUNCEMENT} - 1 bd)")
    print(f"cache path    : {CACHE_PATH}")

    t0 = time.perf_counter()
    result = get_close_eur(TICKER, target)
    elapsed_first = (time.perf_counter() - t0) * 1000
    if result is None:
        print(f"first fetch   : MISS in {elapsed_first:.0f} ms")
        sys.exit(2)
    close_eur, actual = result
    print(f"first fetch   : close={close_eur} EUR on {actual} in {elapsed_first:.0f} ms (network)")

    t0 = time.perf_counter()
    result2 = get_close_eur(TICKER, target)
    elapsed_second = (time.perf_counter() - t0) * 1000
    assert result2 is not None
    close_eur2, actual2 = result2
    print(
        f"second fetch  : close={close_eur2} EUR on {actual2} "
        f"in {elapsed_second:.0f} ms (cache hit)"
    )
    assert (close_eur, actual) == (close_eur2, actual2), "cache returned different values"

    print(f"cache file    : {'CREATED' if CACHE_PATH.exists() else 'MISSING'} ({CACHE_PATH})")
    print(f"speedup       : {elapsed_first / max(elapsed_second, 0.01):.0f}x")


if __name__ == "__main__":
    main()
