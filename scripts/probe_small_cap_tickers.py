"""P9.1c-[F-pre] — probe Yahoo ticker mappings for the small-cap DE targets.

Read-only. For each candidate ISIN -> Yahoo ticker mapping (priority list of
Xetra .DE / Frankfurt .F), tries a 1-month history fetch and records the last
close. Misses are expected for delisted post-OPA small-caps — they will route
to ``manual_review`` in the validation step.

Writes ``data/audits/p91c_small_cap_ticker_probe.csv``. Verified hits feed the
extension of :mod:`src.pricing.target_ticker_resolver`.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yfinance as yf

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "audits" / "p91c_small_cap_ticker_probe.csv"

# (isin, label, candidate Yahoo tickers in priority order). Guesses come from
# the P9.1c-[F] brief; .F is the Frankfurt fallback for the .DE Xetra primary.
CASES: list[tuple[str, str, list[str]]] = [
    ("DE0005490601", "Leo Intl Precision Health", ["LEO.DE", "LEO.F"]),
    ("DE0007279507", "Splendid Medien", ["SPM.F", "SPM.DE"]),
    ("DE000A1E89S5", "Readcrest Capital", ["READ.F", "READ.DE"]),
    ("DE0005653604", "MedNation", ["MEN.F", "MEN.DE"]),
    ("DE000A2NBVD5", "DFV Deutsche Familienversicherung", ["DFV.DE", "DFV.F"]),
    ("DE000A1X3X33", "WCM Beteiligungs", ["WCMK.DE", "WCMK.F"]),
    ("DE000FPH9000", "Francotyp-Postalia", ["FPH.DE", "FPH.F"]),
    ("DE0006569403", "Albis Leasing", ["ALG.DE", "ALG.F"]),
    ("DE0007504508", "Turbon", ["TUR1.DE", "TUR.DE", "TUR1.F"]),
    ("DE0007857476", "Klassik Radio", ["KA8.DE", "KA8.F"]),
    ("DE0007257503", "CECONOMY", ["CEC.DE", "CEC.F"]),
]

FIELDNAMES = ["isin", "label", "ticker_tried", "success", "last_close", "last_date", "notes"]


def _try_ticker(ticker: str) -> tuple[float, str, str] | None:
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
                    "ticker_tried": used,
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
                    "ticker_tried": candidates[0],
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
    print("=" * 72)
    print(f"small-cap DE ticker probe — hit rate {hits}/{len(CASES)} ({rate:.0f}%)")
    print("=" * 72)
    for r in rows:
        flag = "OK " if r["success"] else "MISS"
        print(
            f"  [{flag}] {r['ticker_tried']:<10} {str(r['label'])[:38]:<38} "
            f"{r['last_close']!s:>8} {r['notes']}"
        )
    print(f"CSV: {OUTPUT}")


if __name__ == "__main__":
    main()
