"""Phase 9.1c-[E] — recalc offer_price_total_eur for suspect_mixed deals.

For each deal flagged ``suspect_mixed`` and carrying a populated
``deal_consideration`` row:

  1. Compute T-1bd = announcement_date - 1 business day.
  2. Fetch the acquirer close at T-1bd via yfinance (cached, 30-day TTL).
  3. ``total = (cash_eur or 0) + share_ratio x acquirer_close``.
  4. Audit-only: fetch the target close at T-1bd (best-effort, never fails the
     run).
  5. UPDATE deals: ``offer_price_total_eur=total,
     offer_price_quality_flag='verified_mixed', pricing_source='yfinance_enriched'``.
  6. DELETE the deal's stale scores so Phase-6 re-scores cleanly at [G].

Per-deal transaction. Idempotent (yfinance cache hit + idempotent UPDATE).
On an acquirer-price miss the deal is NOT touched (flag stays
``suspect_mixed``); the script exits with a non-zero code so a downstream
operator notices, instead of a silent half-update.

Outputs ``data/audits/p91c_recalc_results.csv``.

Run (PowerShell, postgres up):
  $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/recalc_offer_price_total.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal, DealConsideration, Score
from src.pricing.recalc import compute_total_eur, prev_business_day
from src.pricing.target_ticker_resolver import isin_from_regulator_ref, resolve_target_ticker
from src.pricing.yfinance_fetcher import get_close_eur

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "audits" / "p91c_recalc_results.csv"

FIELDNAMES = [
    "deal_id",
    "target",
    "cash_eur",
    "share_ratio",
    "acquirer_ticker",
    "acquirer_close",
    "acquirer_date",
    "offer_price_total",
    "target_ticker",
    "target_close",
    "target_date",
    "old_flag",
    "new_flag",
    "scores_deleted",
]


async def _recalc_one(session, deal: Deal, cons: DealConsideration) -> dict[str, object] | None:
    """Returns the CSV row dict, or None on acquirer-price miss (no update)."""
    target_date = prev_business_day(deal.announcement_date)
    acquirer_ticker = cons.acquirer_ticker_yf or ""

    acquirer = get_close_eur(acquirer_ticker, target_date)
    if acquirer is None:
        print(
            f"ERROR deal {deal.id} ({deal.target_name}): "
            f"acquirer price miss for {acquirer_ticker} at {target_date}; not updating.",
            file=sys.stderr,
        )
        return None
    acquirer_close, acquirer_actual = acquirer

    # Audit-only: target close at T-1bd. A miss is non-fatal.
    target_ticker = resolve_target_ticker(isin_from_regulator_ref(deal.regulator_ref))
    target_close = ""
    target_actual = ""
    if target_ticker:
        target_result = get_close_eur(target_ticker, target_date)
        if target_result is not None:
            target_close, target_actual = target_result

    total = compute_total_eur(cons.cash_eur, cons.share_ratio, acquirer_close)

    # Count + delete stale scores; UPDATE deal flags; one transaction.
    scores_deleted = (
        await session.execute(
            select(Score).where(Score.deal_id == deal.id),
        )
    ).all()
    n_scores = len(scores_deleted)
    await session.execute(delete(Score).where(Score.deal_id == deal.id))
    deal.offer_price_total_eur = total
    deal.offer_price_quality_flag = "verified_mixed"
    deal.pricing_source = "yfinance_enriched"
    await session.commit()

    return {
        "deal_id": deal.id,
        "target": deal.target_name,
        "cash_eur": cons.cash_eur if cons.cash_eur is not None else "",
        "share_ratio": cons.share_ratio,
        "acquirer_ticker": acquirer_ticker,
        "acquirer_close": acquirer_close,
        "acquirer_date": acquirer_actual,
        "offer_price_total": total,
        "target_ticker": target_ticker or "",
        "target_close": target_close,
        "target_date": target_actual,
        "old_flag": "suspect_mixed",
        "new_flag": "verified_mixed",
        "scores_deleted": n_scores,
    }


async def _main() -> int:
    rows: list[dict[str, object]] = []
    failures = 0
    sm = get_sessionmaker()
    async with sm() as session:
        deals = (
            (
                await session.execute(
                    select(Deal)
                    .where(Deal.offer_price_quality_flag == "suspect_mixed")
                    .order_by(Deal.id)
                )
            )
            .scalars()
            .all()
        )
        for deal in deals:
            cons = (
                await session.execute(
                    select(DealConsideration).where(DealConsideration.deal_id == deal.id)
                )
            ).scalar_one_or_none()
            if cons is None:
                print(
                    f"ERROR deal {deal.id}: no deal_consideration row — run "
                    "populate_deal_consideration.py first.",
                    file=sys.stderr,
                )
                failures += 1
                continue
            row = await _recalc_one(session, deal, cons)
            if row is None:
                failures += 1
                continue
            rows.append(row)

    await dispose_engine()
    _write_csv(rows)
    _print_summary(rows, failures)
    return 1 if failures else 0


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(rows: list[dict[str, object]], failures: int) -> None:
    print("=" * 72)
    print("P9.1c-[E] - offer_price_total_eur recalc")
    print("=" * 72)
    for r in rows:
        cash = r["cash_eur"] if r["cash_eur"] != "" else "0 (share-only)"
        share = f"{r['share_ratio']} x {r['acquirer_close']} EUR @ {r['acquirer_date']}"
        target = (
            f"target {r['target_ticker']}={r['target_close']} EUR @ {r['target_date']}"
            if r["target_close"] != ""
            else f"target {r['target_ticker']}: miss"
        )
        print(f"  deal {r['deal_id']} {str(r['target'])[:28]:<28}")
        print(f"    cash={cash}, share={share}")
        print(
            f"    -> total={r['offer_price_total']} EUR (flag: {r['old_flag']} -> {r['new_flag']})"
        )
        print(f"    scores deleted: {r['scores_deleted']}; {target}")
    print(f"CSV: {OUTPUT}")
    if failures:
        print(f"FAILURES: {failures}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
