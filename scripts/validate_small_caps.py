"""P9.1c-[F] — validate small-cap DE offer_price against yfinance reference.

For each of the audit's 12 small-cap deals (offer_price < 5 EUR, currently
verified_cash post-P9.1a), fetches the target close at announcement_date - 1
business day and compares it to ``deal.offer_price``:

  * deviation < 30%        → keep ``verified_cash``
  * deviation >= 30%       → downgrade to ``manual_review`` (exceeds_threshold)
  * ticker not in registry → downgrade to ``manual_review`` (ticker_unresolved)
  * yfinance miss          → downgrade to ``manual_review`` (yfinance_miss)

DRY-RUN by default — writes ``data/audits/p91c_small_caps_validation.csv`` but
does NOT touch the DB. Pass ``--apply`` to also UPDATE the deal flags.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal
from src.pricing.recalc import prev_business_day
from src.pricing.target_ticker_resolver import isin_from_regulator_ref, resolve_target_ticker
from src.pricing.yfinance_fetcher import get_close_eur

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "audits" / "p91c_small_caps_validation.csv"

# The user-specified 12 small-cap deal_ids (audit Step-0 outliers minus the 5
# already handled by P9.1a/P9.1b). DFV (1078) is included for sanity-check
# against its P9.1a-corrected 6.60 EUR price.
DEAL_IDS: tuple[int, ...] = (351, 352, 353, 355, 356, 358, 1068, 1071, 1073, 1074, 1077, 1078)

DEVIATION_THRESHOLD = Decimal("0.30")

FIELDNAMES = [
    "deal_id",
    "target_name",
    "isin",
    "offer_price",
    "ticker_yf",
    "target_close_t1",
    "target_date_actual",
    "deviation_pct",
    "old_flag",
    "new_flag",
    "reason",
]


def _classify(
    offer_price: Decimal | None,
    ticker: str | None,
    close: Decimal | None,
) -> tuple[str, Decimal | None, str]:
    """Return (new_flag, deviation_pct, reason)."""
    if ticker is None:
        return ("manual_review", None, "ticker_unresolved")
    if close is None or close <= 0:
        return ("manual_review", None, "yfinance_miss")
    if offer_price is None:
        return ("manual_review", None, "offer_price_null")
    deviation = abs(offer_price - close) / close
    if deviation < DEVIATION_THRESHOLD:
        return ("verified_cash", deviation, "within_threshold")
    return ("manual_review", deviation, "exceeds_30pct_threshold")


async def _validate(apply: bool) -> int:
    rows: list[dict[str, object]] = []
    sm = get_sessionmaker()
    async with sm() as session:
        deals = (
            (await session.execute(select(Deal).where(Deal.id.in_(DEAL_IDS)).order_by(Deal.id)))
            .scalars()
            .all()
        )

        for deal in deals:
            isin = isin_from_regulator_ref(deal.regulator_ref)
            ticker = resolve_target_ticker(isin)
            target_close: Decimal | None = None
            target_date_actual = ""
            if ticker is not None:
                target_date = prev_business_day(deal.announcement_date)
                result = get_close_eur(ticker, target_date, max_lookback_days=5)
                if result is not None:
                    target_close, eff_date = result
                    target_date_actual = eff_date.isoformat()

            new_flag, deviation, reason = _classify(deal.offer_price, ticker, target_close)
            old_flag = deal.offer_price_quality_flag
            rows.append(
                {
                    "deal_id": deal.id,
                    "target_name": deal.target_name,
                    "isin": isin or "",
                    "offer_price": deal.offer_price if deal.offer_price is not None else "",
                    "ticker_yf": ticker or "",
                    "target_close_t1": target_close if target_close is not None else "",
                    "target_date_actual": target_date_actual,
                    "deviation_pct": (f"{deviation * 100:.2f}" if deviation is not None else ""),
                    "old_flag": old_flag,
                    "new_flag": new_flag,
                    "reason": reason,
                }
            )

            if apply and new_flag != old_flag:
                deal.offer_price_quality_flag = new_flag
                await session.commit()

    await dispose_engine()
    _write_csv(rows)
    _print_summary(rows, apply)
    return 0


def _write_csv(rows: list[dict[str, object]]) -> None:
    # Sort: verified_cash first (alphabetical desc on new_flag), then by
    # deviation asc within each group (NULL deviations last via large sentinel).
    def _key(r: dict[str, object]) -> tuple[int, float]:
        flag_order = 0 if r["new_flag"] == "verified_cash" else 1
        try:
            dev = float(str(r["deviation_pct"])) if r["deviation_pct"] != "" else 1e12
        except ValueError:
            dev = 1e12
        return (flag_order, dev)

    rows = sorted(rows, key=_key)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(rows: list[dict[str, object]], apply: bool) -> None:
    by_flag: dict[str, int] = {}
    for r in rows:
        by_flag[str(r["new_flag"])] = by_flag.get(str(r["new_flag"]), 0) + 1
    mode = "APPLIED" if apply else "DRY-RUN"
    print("=" * 80)
    print(f"P9.1c-[F] small-cap validation ({mode})")
    print("=" * 80)
    for r in rows:
        marker = "OK " if r["new_flag"] == "verified_cash" else "MR "
        dev = f"{r['deviation_pct']}%" if r["deviation_pct"] != "" else "—"
        target_close = r["target_close_t1"] if r["target_close_t1"] != "" else "—"
        print(
            f"  [{marker}] {r['deal_id']:>4} {str(r['target_name'])[:32]:<32} "
            f"offer={r['offer_price']!s:<8} close={target_close!s:<10} "
            f"dev={dev:<10} {r['reason']}"
        )
    print(f"\nflag distribution: {by_flag}")
    print(f"CSV: {OUTPUT}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Also UPDATE deals.offer_price_quality_flag in the DB (default: dry-run).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_validate(apply=args.apply)))


if __name__ == "__main__":
    main()
