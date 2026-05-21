"""Phase 8 — Step 0 IBKR pre-flight check.

Validates the IBKR paper-trading environment BEFORE any trading code is written:
connection, paper-account guard, account balance, market-data permissions,
timezone handling, and asset coverage on 6 sample tickers across FR/IT/DE.

Run (IBKR Gateway/TWS must be up on the paper port first):

    .venv/Scripts/python.exe scripts/ibkr_preflight.py

Reads connection config from `Settings` (.env): IBKR_HOST / IBKR_PORT /
IBKR_CLIENT_ID / IBKR_PAPER. Read-only — places NO orders.
"""

from __future__ import annotations

import contextlib
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Allow `from src...` when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and choke on the ✅/○ status glyphs.
for _stream in (sys.stdout, sys.stderr):
    with contextlib.suppress(AttributeError, ValueError):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from ib_async import IB, Stock  # noqa: E402

from src.core.settings import get_settings  # noqa: E402

# (symbol, primaryExchange, currency, human label)
SAMPLE_TICKERS = [
    ("SAN", "SBF", "EUR", "Sanofi (FR / Euronext Paris)"),
    ("AIR", "SBF", "EUR", "Airbus (FR / Euronext Paris)"),
    ("ENEL", "BVME", "EUR", "Enel (IT / Borsa Italiana)"),
    ("ENI", "BVME", "EUR", "Eni (IT / Borsa Italiana)"),
    ("SAP", "IBIS", "EUR", "SAP (DE / Xetra)"),
    ("BAS", "IBIS", "EUR", "BASF (DE / Xetra)"),
]

# IBKR market-data type codes returned per ticker.
MDT = {1: "realtime", 2: "frozen", 3: "delayed", 4: "delayed-frozen"}


def _qualify(ib: IB, symbol: str, exch: str, ccy: str) -> Stock | None:
    """Qualify a stock, trying the primary exchange directly then SMART routing.

    `ib.qualifyContracts` populates `conId` in place on success; on Error 200
    (no security definition) it leaves conId unset. Returns the qualified
    contract or None.
    """
    for routing in (exch, "SMART"):
        c = Stock(symbol, routing, ccy, primaryExchange=exch)
        with contextlib.suppress(Exception):
            ib.qualifyContracts(c)
        if getattr(c, "conId", 0):
            return c
    return None


def main() -> int:
    s = get_settings()
    print("=" * 64)
    print("IBKR PRE-FLIGHT  —  Phase 8 Step 0")
    print("=" * 64)
    print(
        f"host={s.ibkr_host} port={s.ibkr_port} "
        f"client_id={s.ibkr_client_id} paper={s.ibkr_paper}"
    )

    # ---- Guard: paper only (no real-money exposure, ever) -------------------
    paper_ports = {7497, 4002}
    if not s.ibkr_paper or s.ibkr_port not in paper_ports:
        print(
            f"\nABORT: paper guard failed (ibkr_paper={s.ibkr_paper}, "
            f"port={s.ibkr_port} not in {sorted(paper_ports)}). Refusing to connect."
        )
        return 2

    ib = IB()
    try:
        t0 = time.perf_counter()
        ib.connect(s.ibkr_host, s.ibkr_port, clientId=s.ibkr_client_id, timeout=15)
        latency_ms = (time.perf_counter() - t0) * 1000
    except Exception as exc:
        print(f"\nCONNECTION FAILED: {type(exc).__name__}: {exc}")
        print("→ Is IBKR Gateway/TWS running and logged in on the paper port?")
        print("  Check: API enabled, 'Read-Only API' OFF, 127.0.0.1 in trusted IPs.")
        return 1

    try:
        print(f"\n[1] CONNECTION  OK  ({latency_ms:.0f} ms)")
        server_time = ib.reqCurrentTime()  # tz-aware UTC datetime
        local_now = datetime.now().astimezone()
        print("\n[2] TIMEZONE")
        print(f"    IBKR server time (UTC) : {server_time.astimezone(UTC):%Y-%m-%d %H:%M:%S %Z}")
        print(f"    Local machine time     : {local_now:%Y-%m-%d %H:%M:%S %Z}")
        print(f"    Skew vs UTC            : {(local_now - server_time).total_seconds():+.1f}s")

        # ---- Account summary + paper-account assertion ---------------------
        print("\n[3] ACCOUNT")
        rows = ib.accountSummary()
        accounts = sorted({r.account for r in rows})
        print(f"    Accounts: {accounts}")
        for acct in accounts:
            tag = {r.tag: r for r in rows if r.account == acct}
            net = tag.get("NetLiquidation")
            cash = tag.get("TotalCashValue")
            kind = "PAPER ✅" if acct.startswith("DU") else "⚠️ NOT a DU paper account"
            print(
                f"    {acct} [{kind}]  NetLiq={net.value if net else '?'} "
                f"{net.currency if net else ''}  Cash={cash.value if cash else '?'}"
            )

        # ---- Market data + asset coverage on 6 sample tickers -------------
        print("\n[4] MARKET DATA + ASSET COVERAGE (6 tickers, 3 exchanges)")
        ib.reqMarketDataType(3)  # delayed (free tier); enough for the daily 9h cron
        results = []
        for symbol, exch, ccy, label in SAMPLE_TICKERS:
            contract = _qualify(ib, symbol, exch, ccy)
            if contract is None:
                print(f"    ✗ {label:<34} NOT QUALIFIED (no security definition)")
                results.append((label, "not_qualified", None, None))
                continue

            [tk] = ib.reqTickers(contract)
            mdt = MDT.get(getattr(tk, "marketDataType", None), "?")
            price = tk.marketPrice()
            bid, ask, last, close = tk.bid, tk.ask, tk.last, tk.close
            ok = not math.isnan(price)  # NaN ⇒ no data received
            mark = "✓" if ok else "○"
            print(
                f"    {mark} {label:<34} conId={contract.conId} routed={contract.exchange} "
                f"mdt={mdt:<9} bid={bid} ask={ask} last={last} close={close}"
            )
            results.append((label, "qualified", mdt, price))

        qualified_n = sum(1 for _, st, *_ in results if st == "qualified")
        print(f"\n    Qualified: {qualified_n}/{len(SAMPLE_TICKERS)}")
        print("\n" + "=" * 64)
        print(
            f"PRE-FLIGHT DONE — connection {latency_ms:.0f}ms, "
            f"{qualified_n}/6 contracts qualified"
        )
        print("=" * 64)
        return 0 if qualified_n == len(SAMPLE_TICKERS) else 3
    finally:
        ib.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
