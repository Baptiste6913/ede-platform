"""P14 Step 1 — extract ISIN + resolve tickers for the FRESH FR deal pool.

Reuses the Phase-10 ISIN extraction (AMF BDIF PDF, first FR-prefixed ISIN in the
first 2 pages) and the Phase-13 OpenFIGI resolution/persistence, applied to the
*live* fresh pool instead of the historical labelled set:

    FR, announcement_date >= SINCE, completion_label IS NULL, ticker_target NULL

For each deal: extract ISIN -> persist ticker_target -> OpenFIGI resolve ->
persist trading_ticker_yf / ibkr_ticker / ibkr_exchange / ticker_resolution_flag
(cache-aware: already-resolved ISINs are not re-hit). DE deals already carry an
ISIN + home_venue flag and are out of scope here.

NOTE (tech debt P15): ISIN extraction is NOT wired into live ingestion -- this is
a one-shot backfill on the fresh pool, like Phase 10 was on the historical set.

Run (host, Docker postgres on localhost):
    $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
    .venv/Scripts/python.exe scripts/p14_resolve_fresh.py            # DRY-RUN
    .venv/Scripts/python.exe scripts/p14_resolve_fresh.py --apply    # commit

Output: artifacts/phase-14/isin_resolution_fresh.md (tracked).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for the p10 helpers

from p10_isin_extraction_fr import _extract_isin, _local_pdf  # reuse tested logic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal
from src.core.settings import get_settings
from src.pricing.openfigi_resolver import OpenFIGIResolver
from src.pricing.ticker_resolution import apply_resolution, is_isin

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = REPO_ROOT / "artifacts" / "phase-14" / "isin_resolution_fresh.md"
SINCE = date(2025, 12, 3)


async def _resolve_one(deal: Deal, resolver: OpenFIGIResolver) -> str:
    """Resolve a deal's (now-set) ISIN and persist the ticker. Returns flag."""
    result = await asyncio.to_thread(
        resolver.resolve_isin_to_yahoo_ticker, deal.ticker_target or ""
    )
    return apply_resolution(deal, result)


async def _process(*, dry_run: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    resolver = OpenFIGIResolver(settings.openfigi_api_key.get_secret_value())
    rows: list[dict[str, str]] = []

    async with sm() as session:
        deals = list(
            (
                await session.scalars(
                    select(Deal)
                    .where(
                        Deal.juridiction == "FR",
                        Deal.announcement_date >= SINCE,
                        Deal.completion_label.is_(None),
                    )
                    .order_by(Deal.announcement_date.desc())
                )
            ).all()
        )
        print(f"[P14] {len(deals)} fresh FR deals")

        for deal in deals:
            row = {
                "ref": deal.regulator_ref,
                "target": deal.target_name,
                "isin": deal.ticker_target or "",
                "isin_status": "preexisting" if deal.ticker_target else "",
                "ticker": "",
                "flag": "",
            }
            # 1. ISIN extraction (skip if already set).
            if not deal.ticker_target:
                pdf = _local_pdf(deal.pdf_path)
                if pdf is None:
                    row["isin_status"] = "no_pdf"
                    rows.append(row)
                    continue
                isin, status = _extract_isin(pdf)
                if isin is None:
                    row["isin_status"] = status  # no_isin / pdf_error:*
                    rows.append(row)
                    continue
                deal.ticker_target = isin
                row["isin"] = isin
                row["isin_status"] = "extracted"

            # 2. OpenFIGI resolution + persistence.
            if is_isin(deal.ticker_target):
                flag = await _resolve_one(deal, resolver)
                row["flag"] = flag
                row["ticker"] = deal.trading_ticker_yf or ""
            rows.append(row)

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()
    _write_md(rows, dry_run=dry_run)
    flags = Counter(r["flag"] for r in rows if r["flag"])
    isin_ok = sum(1 for r in rows if r["isin"])
    print(f"[P14] mode={'DRY-RUN' if dry_run else 'APPLY'} isin_ok={isin_ok}/{len(rows)}")
    print(f"[P14] flags={dict(sorted(flags.items()))}")
    print(f"[P14] audit -> {OUT_MD}")


def _write_md(rows: list[dict[str, str]], *, dry_run: bool) -> None:
    flags = Counter(r["flag"] for r in rows if r["flag"])
    isin_ok = sum(1 for r in rows if r["isin"])
    home = sum(1 for r in rows if r["flag"] == "home_venue")
    lines = ["# Phase 14 Step 1 — ISIN extraction + resolution (fresh FR pool)", ""]
    if dry_run:
        lines.append("> DRY-RUN (no DB writes).")
        lines.append("")
    lines.append(
        f"Fresh FR deals: **{len(rows)}** · ISIN resolved: **{isin_ok}** · "
        f"home_venue (tradable): **{home}**"
    )
    lines.append("")
    lines.append("## Resolution flag distribution")
    lines.append("")
    lines.append("| flag | count |")
    lines.append("|---|---:|")
    for flag, n in sorted(flags.items()):
        lines.append(f"| `{flag}` | {n} |")
    lines.append("")
    lines.append("## Per deal")
    lines.append("")
    lines.append("| ref | target | ISIN | ticker | flag |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['ref']} | {r['target'][:26]} | {r['isin'] or r['isin_status'] or '-'} "
            f"| {r['ticker'] or '-'} | `{r['flag'] or r['isin_status'] or '-'}` |"
        )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="P14 fresh FR ISIN extraction + resolution")
    p.add_argument("--apply", action="store_true", help="commit (default = dry-run)")
    args = p.parse_args()
    asyncio.run(_process(dry_run=not args.apply))
