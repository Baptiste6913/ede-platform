"""P11 Step 3 — full premium_pct backfill via OpenFIGI (home_venue main-market).

Decision (Step 2.6): auto-backfill ONLY main-market resolutions (home_venue,
venue_fallback) with the premium sanity gate enforced. Euronext Growth
(home_venue_growth) is UNSAFE (ALCLA.PA→Claranova collision) → routed to
manual_review, never auto-priced. IT/Consob deals have no ISIN (ticker_target
IS NULL) and are excluded by the query.

Per deal (labelled + ticker_target NOT NULL):
1. Resolve ticker_target (an ISIN) via OpenFIGI (batched, 100 jobs/req).
2. Branch on the resolution source flag:
   - home_venue / venue_fallback → PROCEED (price + gate).
   - home_venue_growth          → SKIP, flag, manual_review.
   - no_match / unknown_exch     → SKIP, flag.
   - non-ISIN ticker_target      → SKIP, flag 'not_isin'.
3. PROCEED: target_date = announcement_date - 1 business day; fetch close (EUR)
   via yfinance; if no data → flag 'no_price_data'.
4. Sanity gate: premium_pct = (offer - ref) / ref (a *fraction* — scoring x100).
   If the implied percentage is outside [-50 %, +200 %] → flag
   'premium_out_of_bounds', store the reference price but leave premium_pct NULL
   (keeps the wrong-ticker / corrupt-offer rows out of the training set).
5. Persist reference_price_* + premium_pct + ticker_resolution_flag.

Resume: deals whose ticker_resolution_flag is already set are skipped unless
``--force`` is passed.

Outputs:
- ``artifacts/phase-11/full_backfill_audit.md`` (tracked)
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal
from src.core.settings import get_settings
from src.pricing.openfigi_resolver import CACHE_PATH, OpenFIGIResolver, OpenFIGISource
from src.pricing.yfinance_fetcher import get_close_eur

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = REPO_ROOT / "artifacts" / "phase-11" / "full_backfill_audit.md"

PREMIUM_HIGH_PCT = 200.0
PREMIUM_LOW_PCT = -50.0
_ISIN_LEN = 12
_WEEKEND_START = 5  # Sat

# Source flags that proceed to pricing.
_PRICE_OK_SOURCES = {OpenFIGISource.HOME_VENUE, OpenFIGISource.VENUE_FALLBACK}


def _is_isin(value: str | None) -> bool:
    return bool(value and len(value) == _ISIN_LEN and value.isalnum() and value[:2].isalpha())


def _prev_business_day(d: date) -> date:
    candidate = d - timedelta(days=1)
    while candidate.weekday() >= _WEEKEND_START:
        candidate -= timedelta(days=1)
    return candidate


def _resolve_all(resolver: OpenFIGIResolver, deals: list[Deal]) -> dict[str, object]:
    isins = sorted({d.ticker_target for d in deals if _is_isin(d.ticker_target)})
    isins_str = [i for i in isins if i is not None]
    return resolver.resolve_batch(isins_str)


def _backfill_deal(deal: Deal, resolved: dict[str, object]) -> dict[str, object]:
    """Mutate ``deal`` in place; return an audit row."""
    row: dict[str, object] = {
        "deal_id": deal.id,
        "juridiction": deal.juridiction,
        "regulator_ref": deal.regulator_ref,
        "target_name": deal.target_name,
        "isin": deal.ticker_target or "",
        "yahoo_ticker": "",
        "exch_bbg": "",
        "premium_pct": "",
        "flag": "",
    }
    if not _is_isin(deal.ticker_target):
        deal.ticker_resolution_flag = "not_isin"
        row["flag"] = "not_isin"
        return row

    res = resolved.get(deal.ticker_target or "")
    if res is None:  # should not happen — every valid ISIN was batched
        deal.ticker_resolution_flag = "no_match"
        row["flag"] = "no_match"
        return row

    source: OpenFIGISource = res.source  # type: ignore[attr-defined]
    row["yahoo_ticker"] = res.yahoo_ticker or ""  # type: ignore[attr-defined]
    row["exch_bbg"] = res.exch_code_bbg or ""  # type: ignore[attr-defined]

    if source not in _PRICE_OK_SOURCES:
        # home_venue_growth (manual_review), no_match, unknown_exch.
        deal.ticker_resolution_flag = str(source).replace("openfigi_", "")
        row["flag"] = str(deal.ticker_resolution_flag)
        return row

    ticker: str = res.yahoo_ticker  # type: ignore[attr-defined]
    target_date = _prev_business_day(deal.announcement_date)
    try:
        priced = get_close_eur(ticker, target_date, max_lookback_days=5)
    except Exception:  # audit script never crashes on a single deal
        priced = None
    if priced is None:
        deal.ticker_resolution_flag = "no_price_data"
        row["flag"] = "no_price_data"
        return row

    close_eur, eff_date = priced
    deal.reference_price_at_announcement = close_eur
    deal.reference_price_source = "openfigi+yfinance"
    deal.reference_price_target_date = target_date
    deal.reference_price_effective_date = eff_date

    if deal.offer_price is not None and close_eur > 0:
        premium = (deal.offer_price - close_eur) / close_eur  # fraction
        pct = float(premium) * 100.0
        if pct > PREMIUM_HIGH_PCT or pct < PREMIUM_LOW_PCT:
            deal.ticker_resolution_flag = "premium_out_of_bounds"
            deal.premium_pct = None  # keep garbage out of the training set
            row["flag"] = "premium_out_of_bounds"
            row["premium_pct"] = f"{pct:.2f}"
            return row
        deal.premium_pct = premium.quantize(Decimal("0.0001"))
        row["premium_pct"] = f"{pct:.2f}"

    deal.ticker_resolution_flag = str(source).replace("openfigi_", "")
    row["flag"] = str(deal.ticker_resolution_flag)
    return row


def _write_md(rows: list[dict[str, object]], total_labelled: int, skipped_resume: int) -> None:
    flags: Counter[str] = Counter(str(r["flag"]) for r in rows)
    premium_vals = [
        float(str(r["premium_pct"]))
        for r in rows
        if r["premium_pct"] and r["flag"] != "premium_out_of_bounds"
    ]
    priced = sum(1 for r in rows if r["flag"] in ("home_venue", "venue_fallback"))
    with_premium = len(premium_vals)

    lines: list[str] = []
    lines.append("# Phase 11 Step 3 — full premium_pct backfill (OpenFIGI home_venue)\n")
    lines.append(
        f"Processed **{len(rows)}** deals this run (resume-skipped "
        f"{skipped_resume} already-flagged). Auto-backfill restricted to "
        "main-market resolutions (home_venue / venue_fallback) with the premium "
        "sanity gate enforced; home_venue_growth routed to manual_review.\n"
    )

    lines.append("## Distribution by flag\n")
    lines.append("| ticker_resolution_flag | Count |")
    lines.append("|---|---:|")
    for flag in sorted(flags):
        lines.append(f"| `{flag}` | {flags[flag]} |")
    lines.append(f"| **TOTAL processed** | **{len(rows)}** |")
    lines.append("")

    lines.append("## Coverage\n")
    lines.append(f"- Deals with a usable `premium_pct` (gate-passed): **{with_premium}**.")
    lines.append(f"- Deals priced (home_venue/venue_fallback reached pricing): {priced}.")
    lines.append(f"- Labelled deals total (incl. IT no-ISIN, not in this run): {total_labelled}.")
    lines.append("")

    if premium_vals:
        lines.append("## premium_pct distribution (gate-passed, shown as %)\n")
        lines.append(f"- count : {len(premium_vals)}")
        lines.append(f"- mean  : {statistics.mean(premium_vals):.2f} %")
        lines.append(f"- median: {statistics.median(premium_vals):.2f} %")
        lines.append(f"- min   : {min(premium_vals):.2f} %")
        lines.append(f"- max   : {max(premium_vals):.2f} %")
        if len(premium_vals) > 1:
            lines.append(f"- stdev : {statistics.stdev(premium_vals):.2f} %")
        lines.append("")

    oob = [r for r in rows if r["flag"] == "premium_out_of_bounds"]
    lines.append("## Outliers gate-caught (premium_out_of_bounds)\n")
    if oob:
        lines.append("| Ref | Target | ISIN | Ticker | premium % | likely cause |")
        lines.append("|---|---|---|---|---:|---|")
        for r in oob:
            lines.append(
                f"| {r['regulator_ref']} | {str(r['target_name'])[:22]} | {r['isin']} | "
                f"{r['yahoo_ticker']} | {r['premium_pct']} | wrong-ticker or corrupt offer_price |"
            )
    else:
        lines.append("- none.")
    lines.append("")

    lines.append("## manual_review queue (growth + no_match + unknown_exch + not_isin)\n")
    review = [
        r
        for r in rows
        if r["flag"] in ("home_venue_growth", "no_match", "unknown_exch", "not_isin")
    ]
    lines.append(f"- {len(review)} deals flagged for manual review (excluded from auto-backfill).")
    lines.append("")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="reprocess already-flagged deals")
    parser.add_argument("--dry-run", action="store_true", help="resolve+price but do not commit")
    args = parser.parse_args()

    key = get_settings().openfigi_api_key.get_secret_value()
    if not key:
        sys.exit("OPENFIGI_API_KEY missing from environment/.env")
    resolver = OpenFIGIResolver(key, cache_path=CACHE_PATH, use_cache=True)

    engine = create_async_engine(get_settings().database_url, echo=False, future=True)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sm() as session:
        all_labelled = (
            (await session.execute(select(Deal).where(Deal.completion_label.isnot(None))))
            .scalars()
            .all()
        )
        deals = [
            d
            for d in all_labelled
            if d.ticker_target is not None and (args.force or d.ticker_resolution_flag is None)
        ]
        skipped_resume = sum(
            1
            for d in all_labelled
            if d.ticker_target is not None
            and not args.force
            and d.ticker_resolution_flag is not None
        )
        print(f"[STEP-3] {len(deals)} deals to process ({skipped_resume} resume-skipped)")

        resolved = _resolve_all(resolver, deals)
        rows: list[dict[str, object]] = []
        for idx, deal in enumerate(deals, start=1):
            row = _backfill_deal(deal, resolved)
            rows.append(row)
            print(
                f"[STEP-3] {idx}/{len(deals)} {deal.juridiction} {deal.regulator_ref} "
                f"-> {row['yahoo_ticker'] or '-':12} flag={row['flag']}"
            )

        if args.dry_run:
            print("[STEP-3] dry-run — rolling back")
            await session.rollback()
        else:
            await session.commit()
    await engine.dispose()

    _write_md(rows, total_labelled=len(all_labelled), skipped_resume=skipped_resume)
    flags = Counter(str(r["flag"]) for r in rows)
    with_premium = sum(
        1 for r in rows if r["premium_pct"] and r["flag"] in ("home_venue", "venue_fallback")
    )
    print()
    print(f"flags: {dict(flags)}")
    print(f"usable premium_pct: {with_premium}")
    print(f"MD: {OUT_MD}")


if __name__ == "__main__":
    asyncio.run(main())
