"""P10 Step 3 — sample-test the yfinance reference-price fetcher on 20
labelled deals (mix FR / IT / DE proportional) to drive the Option C
go/no-go decision before the full backfill (Step 4).

For each sampled deal:

1. Resolve ticker via ``resolve_target_ticker(isin, allow_bare_isin=True)``.
   The new Phase 10 fallback passes the bare ISIN to yfinance when no
   curated mapping exists.
2. Compute target_date = announcement_date - 1 business day. Weekend /
   holiday lookback is handled inside ``get_close_eur`` (up to 5
   business days).
3. Call ``get_close_eur(ticker, target_date)`` and record the result.
4. If the price comes back, compute the implied premium_pct vs the
   stored offer_price as a sanity preview (no DB write).

Outputs:
- ``data/audits/p10_sample_yfinance_test.csv`` (gitignored)
- ``docs/phase-10/sample_yfinance_audit.md`` (tracked)

Go-criterion per Option C: overall success rate ≥ 70 % → green-light
the full backfill on the labelled set. Below that → scope-back report
to user for the final decision (DE-only fallback vs. extending IT ISIN
extraction first).
"""

from __future__ import annotations

import asyncio
import csv
import random
import statistics
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal
from src.core.settings import get_settings
from src.pricing.target_ticker_resolver import resolve_target_ticker
from src.pricing.yfinance_fetcher import get_close_eur

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "data" / "audits" / "p10_sample_yfinance_test.csv"
OUT_MD = REPO_ROOT / "docs" / "phase-10" / "sample_yfinance_audit.md"

SEED = 20260601
PROPORTIONAL_QUOTA = {"FR": 13, "IT": 3, "DE": 4}  # ~148/35/39 proportional → 20 total
GO_THRESHOLD = 0.70
PREMIUM_HIGH_OUTLIER = 100.0  # %
PREMIUM_LOW_OUTLIER = -50.0  # %


def _prev_business_day(d: date) -> date:
    """Walk back one calendar day; if it lands on a weekend, walk to the
    previous Friday. ``get_close_eur`` further handles holiday lookback."""
    candidate = d - timedelta(days=1)
    while candidate.weekday() >= 5:  # Sat=5, Sun=6  # noqa: PLR2004
        candidate -= timedelta(days=1)
    return candidate


async def _build_sample() -> list[Deal]:
    engine = create_async_engine(get_settings().database_url, echo=False, future=True)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sm() as session:
        deals = (
            (
                await session.execute(
                    select(Deal).where(Deal.completion_label.isnot(None)).order_by(Deal.id)
                )
            )
            .scalars()
            .all()
        )
    await engine.dispose()

    by_jur: dict[str, list[Deal]] = {"FR": [], "IT": [], "DE": []}
    for d in deals:
        if d.juridiction in by_jur:
            by_jur[d.juridiction].append(d)

    rng = random.Random(SEED)  # noqa: S311 — audit reproducibility, not crypto
    sample: list[Deal] = []
    for jur, quota in PROPORTIONAL_QUOTA.items():
        pool = by_jur.get(jur, [])
        k = min(quota, len(pool))
        sample.extend(rng.sample(pool, k))
    return sample


def _probe(deal: Deal) -> dict[str, object]:
    """Run the full ticker → reference_price chain on a single deal."""
    ann_date = deal.announcement_date
    target_date = _prev_business_day(ann_date) if ann_date else None

    ticker = resolve_target_ticker(deal.ticker_target, allow_bare_isin=True)
    row: dict[str, object] = {
        "deal_id": deal.id,
        "juridiction": deal.juridiction,
        "regulator_ref": deal.regulator_ref,
        "target_name": deal.target_name,
        "isin_or_ticker": deal.ticker_target or "",
        "resolved_ticker": ticker or "",
        "announcement_date": ann_date.isoformat() if ann_date else "",
        "target_date": target_date.isoformat() if target_date else "",
        "offer_price": str(deal.offer_price) if deal.offer_price is not None else "",
        "reference_price_eur": "",
        "effective_date": "",
        "premium_pct": "",
        "status": "",
    }
    if ticker is None:
        row["status"] = "no_ticker"
        return row
    if target_date is None:
        row["status"] = "no_announcement_date"
        return row

    try:
        result = get_close_eur(ticker, target_date, max_lookback_days=5)
    except Exception as exc:
        row["status"] = f"fetch_error:{type(exc).__name__}"
        return row
    if result is None:
        row["status"] = "no_data"
        return row

    close_eur, eff_date = result
    row["reference_price_eur"] = str(close_eur)
    row["effective_date"] = eff_date.isoformat()
    if deal.offer_price is not None and close_eur > 0:
        premium = (deal.offer_price - close_eur) / close_eur
        row["premium_pct"] = f"{premium * 100:.2f}"
    row["status"] = "ok"
    return row


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "deal_id",
        "juridiction",
        "regulator_ref",
        "target_name",
        "isin_or_ticker",
        "resolved_ticker",
        "announcement_date",
        "target_date",
        "offer_price",
        "reference_price_eur",
        "effective_date",
        "premium_pct",
        "status",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_md(rows: list[dict[str, object]]) -> None:  # noqa: PLR0915 — linear narrative
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    by_jur_total: Counter[str] = Counter(str(r["juridiction"]) for r in rows)
    by_jur_ok: Counter[str] = Counter(str(r["juridiction"]) for r in rows if r["status"] == "ok")
    overall_ok = sum(1 for r in rows if r["status"] == "ok")
    overall_rate = overall_ok / total if total else 0.0

    premium_values: list[float] = []
    for r in rows:
        if r["premium_pct"]:
            try:
                premium_values.append(float(str(r["premium_pct"])))
            except ValueError:
                continue

    lines: list[str] = []
    lines.append("# Phase 10 Step 3 — yfinance sample test audit\n")
    lines.append(
        "Tests the full chain `resolve_target_ticker(allow_bare_isin=True) -> "
        "get_close_eur(...)` on 20 labelled deals (mix FR / IT / DE "
        "proportional). Drives the Option C go / no-go decision for the full "
        "Step 4 backfill.\n"
    )
    lines.append("## 1. Success rates\n")
    lines.append("| Jurisdiction | Sample | OK | Rate |")
    lines.append("|---|---:|---:|---:|")
    for jur in ("FR", "IT", "DE"):
        tot = by_jur_total.get(jur, 0)
        ok = by_jur_ok.get(jur, 0)
        rate = (ok / tot * 100.0) if tot else 0.0
        lines.append(f"| {jur} | {tot} | {ok} | {rate:.1f} % |")
    lines.append(f"| **TOTAL** | **{total}** | **{overall_ok}** | **{overall_rate * 100:.1f} %** |")
    lines.append("")

    lines.append("## 2. Status distribution\n")
    counts = Counter(str(r["status"]) for r in rows)
    lines.append("| Status | Count |")
    lines.append("|---|---:|")
    for st in sorted(counts):
        lines.append(f"| `{st}` | {counts[st]} |")
    lines.append("")

    if premium_values:
        lines.append("## 3. Implied premium_pct distribution (sanity preview)\n")
        lines.append("Computed as `(offer_price - reference_price) / reference_price * 100`.\n")
        lines.append(f"- count : {len(premium_values)}")
        lines.append(f"- min   : {min(premium_values):.2f} %")
        lines.append(f"- median: {statistics.median(premium_values):.2f} %")
        lines.append(f"- max   : {max(premium_values):.2f} %")
        if len(premium_values) > 1:
            lines.append(f"- stdev : {statistics.stdev(premium_values):.2f} %")
        outliers = [
            v for v in premium_values if v > PREMIUM_HIGH_OUTLIER or v < PREMIUM_LOW_OUTLIER
        ]
        if outliers:
            lines.append(
                f"- outliers (|premium| > {PREMIUM_HIGH_OUTLIER:.0f} % "
                f"or < {PREMIUM_LOW_OUTLIER:.0f} %) : "
                f"{len(outliers)} -- investigate before Step 4."
            )
        lines.append("")

    lines.append("## 4. Per-deal detail\n")
    lines.append(
        "| Jur | Ref | Target | Ticker resolved | Offer | Ref EUR | Eff date | Premium % | Status |"
    )
    lines.append("|---|---|---|---|---:|---:|---|---:|---|")
    for r in rows:
        lines.append(
            f"| {r['juridiction']} | {r['regulator_ref']} | "
            f"{str(r['target_name'])[:25]} | {r['resolved_ticker']} | "
            f"{r['offer_price']} | {r['reference_price_eur']} | "
            f"{r['effective_date']} | {r['premium_pct']} | `{r['status']}` |"
        )
    lines.append("")

    lines.append("## 5. Go / no-go (Option C criterion)\n")
    lines.append(f"- Threshold: overall success rate ≥ {GO_THRESHOLD * 100:.0f} %.")
    if overall_rate >= GO_THRESHOLD:
        lines.append(
            f"- **GO** ({overall_rate * 100:.1f} % ≥ {GO_THRESHOLD * 100:.0f} %). "
            "Proceed to Step 4 (migration 0016 + full backfill on the 222 "
            "labelled deals)."
        )
    else:
        lines.append(
            f"- **NO-GO** ({overall_rate * 100:.1f} % < {GO_THRESHOLD * 100:.0f} %). "
            "Scope-back options to validate with user:"
        )
        lines.append(
            "  - **A** — DE-only Phase 10 (skip FR + IT in backfill). 39 deals "
            "= 17.6 % of training set."
        )
        lines.append(
            "  - **B** — extend IT ISIN extraction (mirror Step 1 on Consob "
            "PDFs) before scope decision."
        )
        lines.append(
            "  - **C** — extend the curated TARGET_TICKER_MAP with the failing "
            "bare-ISIN cases (manual research, longer)."
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


async def main() -> None:
    print("[STEP-3] building 20-deal proportional sample ...")
    sample = await _build_sample()
    by_jur = Counter(d.juridiction for d in sample)
    print(f"[STEP-3] sample composition: {dict(by_jur)}")
    print()

    rows: list[dict[str, object]] = []
    for idx, deal in enumerate(sample, start=1):
        print(
            f"[STEP-3] {idx}/{len(sample)}  {deal.juridiction}  {deal.regulator_ref}  "
            f"{deal.target_name[:30]}"
        )
        row = _probe(deal)
        rows.append(row)
        ref_price = row["reference_price_eur"]
        status = row["status"]
        print(f"           -> status={status}  ref_price={ref_price}")

    _write_csv(rows)
    _write_md(rows)
    overall_ok = sum(1 for r in rows if r["status"] == "ok")
    rate = overall_ok / len(rows) if rows else 0.0
    print()
    print(f"overall success: {overall_ok}/{len(rows)} = {rate * 100:.1f} %")
    print(f"CSV : {OUT_CSV}")
    print(f"MD  : {OUT_MD}")


if __name__ == "__main__":
    asyncio.run(main())
