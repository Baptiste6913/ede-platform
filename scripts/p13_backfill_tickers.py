"""P13 — backfill the persisted trading ticker from OpenFIGI resolution.

Phase 11 resolved ISIN → ticker but discarded the ticker (only the flag +
reference price were stored). Phase 13 needs it persisted (``trading_ticker_yf``
for the yfinance price provider, ``ibkr_ticker`` / ``ibkr_exchange`` for the
executor). This one-shot populates those columns for every deal carrying an ISIN
whose ticker is not yet stored, reusing the OpenFIGI on-disk cache (the 93 ISINs
resolved in Phase 11 are free — no API calls).

Resolution provenance is written to ``ticker_resolution_flag`` only when it is
currently NULL or already a resolution flag; a *processing-outcome* flag
(premium_out_of_bounds / no_price_data / manual_review) is PRESERVED so the
Phase-11 premium gate is not undone (see ticker_resolution.PROCESSING_OUTCOME_FLAGS).

Run (host, Docker postgres mapped to localhost):
    $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
    .venv/Scripts/python.exe scripts/p13_backfill_tickers.py          # cache-only
    .venv/Scripts/python.exe scripts/p13_backfill_tickers.py --force  # re-derive all

Output: artifacts/phase-13/ticker_backfill_audit.md (tracked).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal
from src.core.settings import get_settings
from src.pricing.openfigi_resolver import OpenFIGIResolver
from src.pricing.ticker_resolution import (
    PROCESSING_OUTCOME_FLAGS,
    apply_resolution,
    is_isin,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = REPO_ROOT / "artifacts" / "phase-13" / "ticker_backfill_audit.md"


def _backfill_one(deal: Deal, result: object) -> str:
    """Apply a resolution, preserving any processing-outcome flag. Returns flag."""
    prior = deal.ticker_resolution_flag
    apply_resolution(deal, result)  # type: ignore[arg-type]
    if prior in PROCESSING_OUTCOME_FLAGS:
        deal.ticker_resolution_flag = prior  # keep premium/price gate outcome
    return str(deal.ticker_resolution_flag)


def _write_md(rows: list[dict[str, object]]) -> None:
    by_flag: Counter[str] = Counter(str(r["flag"]) for r in rows)
    by_jur_flag: Counter[tuple[str, str]] = Counter(
        (str(r["juridiction"]), str(r["flag"])) for r in rows
    )
    fr_home = [
        r for r in rows if r["juridiction"] == "FR" and r["flag"] == "home_venue" and r["yahoo"]
    ]
    lines: list[str] = ["# Phase 13 — ticker backfill audit", ""]
    lines.append(f"Deals processed (ISIN, ticker not yet stored): **{len(rows)}**")
    lines.append("")
    lines.append("## Persisted flag distribution")
    lines.append("")
    lines.append("| flag | count |")
    lines.append("|---|---:|")
    for flag, n in sorted(by_flag.items()):
        lines.append(f"| `{flag}` | {n} |")
    lines.append("")
    lines.append("## By jurisdiction x flag")
    lines.append("")
    lines.append("| jurisdiction | flag | count |")
    lines.append("|---|---|---:|")
    for (jur, flag), n in sorted(by_jur_flag.items()):
        lines.append(f"| {jur} | `{flag}` | {n} |")
    lines.append("")
    lines.append(f"## FR home_venue with clean ticker persisted — {len(fr_home)}")
    lines.append("")
    lines.append("| ISIN | yahoo (price) | ibkr_ticker | ibkr_exchange |")
    lines.append("|---|---|---|---|")
    for r in sorted(fr_home, key=lambda x: str(x["isin"])):
        lines.append(f"| {r['isin']} | {r['yahoo']} | {r['ibkr']} | {r['exch']} |")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run(force: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    resolver = OpenFIGIResolver(settings.openfigi_api_key.get_secret_value())

    async with sessionmaker() as session:
        deals = list((await session.scalars(select(Deal))).all())
        targets = [
            d for d in deals if is_isin(d.ticker_target) and (force or d.trading_ticker_yf is None)
        ]
        isins = sorted({d.ticker_target for d in targets if d.ticker_target})
        resolved = resolver.resolve_batch(isins)

        rows: list[dict[str, object]] = []
        for deal in targets:
            result = resolved.get(deal.ticker_target or "")
            if result is None:
                deal.ticker_resolution_flag = deal.ticker_resolution_flag or "no_match"
                flag = str(deal.ticker_resolution_flag)
            else:
                flag = _backfill_one(deal, result)
            rows.append(
                {
                    "deal_id": deal.id,
                    "juridiction": deal.juridiction,
                    "isin": deal.ticker_target,
                    "flag": flag,
                    "yahoo": deal.trading_ticker_yf or "",
                    "ibkr": deal.ibkr_ticker or "",
                    "exch": deal.ibkr_exchange or "",
                }
            )
        await session.commit()

    await engine.dispose()
    _write_md(rows)
    by_flag = Counter(str(r["flag"]) for r in rows)
    print(f"processed={len(rows)} flags={dict(sorted(by_flag.items()))}")
    print(f"audit -> {OUT_MD}")


def main() -> None:
    parser = argparse.ArgumentParser(description="P13 ticker backfill")
    parser.add_argument("--force", action="store_true", help="re-derive even if already stored")
    args = parser.parse_args()
    asyncio.run(run(args.force))


if __name__ == "__main__":
    main()
