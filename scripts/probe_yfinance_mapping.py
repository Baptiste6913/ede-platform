"""P9.1c STEP 0 — probe ISIN -> Yahoo ticker mapping (read-only, no DB).

For each critical deal/acquirer, try the derived Yahoo ticker(s) and fetch the
last EOD closes. German listings are tried on Xetra (.DE) then Frankfurt (.F).
Writes data/audits/p91c_yfinance_mapping.csv + a hit-rate summary.

Run:
  .venv/Scripts/python.exe scripts/probe_yfinance_mapping.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import yfinance as yf

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "audits" / "p91c_yfinance_mapping.csv"

# (isin, label, [candidate Yahoo tickers in priority order])
CASES: list[tuple[str, str, list[str]]] = [
    ("DE000CBK1001", "Commerzbank (target)", ["CBK.DE", "CBK.F"]),
    ("DE000PSM7770", "ProSiebenSat.1 (target)", ["PSM.DE", "PSM.F"]),
    ("IT0005239360", "UniCredit (acquirer)", ["UCG.MI"]),
    ("NL0015001OI1", "MFE A (acquirer)", ["MFEA.MI", "MFE.MI"]),
    ("DE000A2QRHL6", "Linus (target)", ["LINU.DE", "LINU.F"]),
]

FIELDNAMES = ["isin", "label", "derived_ticker", "success", "last_close", "last_date", "notes"]


def _try_ticker(ticker: str) -> tuple[float, str, str] | None:
    """Return (last_close, last_date_iso, currency) or None if no data."""
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
    except Exception:
        return None
    if hist is None or hist.empty or "Close" not in hist:
        return None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None
    last_dt = closes.index[-1]
    currency = ""
    try:
        currency = str(yf.Ticker(ticker).fast_info.get("currency") or "")
    except Exception:
        currency = ""
    return (round(float(closes.iloc[-1]), 4), last_dt.date().isoformat(), currency)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    hits = 0
    for isin, label, candidates in CASES:
        matched: tuple[float, str, str] | None = None
        used = candidates[0]
        for cand in candidates:
            res = _try_ticker(cand)
            if res is not None:
                matched = res
                used = cand
                break
        if matched is not None:
            hits += 1
            last_close, last_date, currency = matched
            note = f"currency={currency}"
            if used != candidates[0]:
                note += f"; fell back from {candidates[0]}"
            rows.append(
                {
                    "isin": isin,
                    "label": label,
                    "derived_ticker": used,
                    "success": True,
                    "last_close": last_close,
                    "last_date": last_date,
                    "notes": note,
                }
            )
        else:
            rows.append(
                {
                    "isin": isin,
                    "label": label,
                    "derived_ticker": candidates[0],
                    "success": False,
                    "last_close": "",
                    "last_date": "",
                    "notes": f"no data for any of {candidates}",
                }
            )

    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    rate = hits / len(CASES) * 100
    print("=" * 60)
    print(f"yfinance mapping probe — hit rate {hits}/{len(CASES)} ({rate:.0f}%)")
    print("=" * 60)
    for r in rows:
        flag = "OK " if r["success"] else "MISS"
        print(
            f"  [{flag}] {r['derived_ticker']:<9} {r['label']:<26} {r['last_close']} {r['notes']}"
        )
    print(f"CSV: {OUTPUT}")


if __name__ == "__main__":
    main()
