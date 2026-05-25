"""Audit BaFin (DE) offer_price outliers — Phase 9.1 STEP 0 (read-only).

Flags deals whose parsed `offer_price` is implausible for the BaFin source
(`juridiction='DE'`): too low (< EUR 5), too high (> EUR 500), or NULL. These
are the candidates the Phase-9.1 parser fix must correct — e.g. the Commerzbank
deal stored at EUR 1.00 against a real ~EUR 16-18 quote, which corrupts the
Phase-6 spread and disqualifies the deal from Phase-8 trading.

For context each row carries a best-effort `premarket_price`: the last stored
close for the target ticker strictly before the announcement date (blank when
no price history exists). A genuine offer sits at a premium above it; a EUR 1.00
"offer" next to a EUR 16 premarket is an obvious parser failure.

Outputs:
  - data/audits/p91_offer_price_audit.csv
  - a console summary (count per bucket)

Run (PowerShell, repo root, postgres up):
  $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/audit_offer_price.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path

# Standalone invocation: make `src` importable before the first-party imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal, Price

LOW_THRESHOLD = Decimal("5")
HIGH_THRESHOLD = Decimal("500")

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "audits" / "p91_offer_price_audit.csv"

FIELDNAMES = [
    "deal_id",
    "regulator_ref",
    "target_company",
    "offer_price",
    "currency",
    "premarket_price",
    "bucket",
    "announcement_date",
    "source_pdf_url",
    "pdf_path",
]


def _bucket(price: Decimal | None) -> str:
    if price is None:
        return "null"
    if price < LOW_THRESHOLD:
        return "suspect_low"
    if price > HIGH_THRESHOLD:
        return "suspect_high"
    return "ok"  # not reached given the query filter; keeps the mapping total


async def _premarket_price(session: AsyncSession, deal: Deal) -> Decimal | None:
    """Last stored close for the target ticker strictly before announcement.

    Best-effort context only — returns None when the ticker is unknown or no
    price history is stored.
    """
    if not deal.ticker_target:
        return None
    cutoff = datetime.combine(deal.announcement_date, time.min, tzinfo=UTC)
    stmt = (
        select(Price.close)
        .where(Price.ticker == deal.ticker_target, Price.ts < cutoff)
        .order_by(Price.ts.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(total_de: int, counts: dict[str, int], n_rows: int) -> None:
    pct = (n_rows / total_de * 100) if total_de else 0.0
    print("=" * 60)
    print("BaFin offer_price audit (Phase 9.1 STEP 0)")
    print("=" * 60)
    print(f"BaFin (DE) deals total : {total_de}")
    print(f"outliers flagged       : {n_rows}  ({pct:.1f}%)")
    print(f"  suspect_low  (< {LOW_THRESHOLD} EUR) : {counts['suspect_low']}")
    print(f"  suspect_high (> {HIGH_THRESHOLD} EUR): {counts['suspect_high']}")
    print(f"  null                    : {counts['null']}")
    print(f"CSV: {OUTPUT}")


async def _audit() -> None:
    counts = {"suspect_low": 0, "suspect_high": 0, "null": 0}
    rows: list[dict[str, object]] = []
    sm = get_sessionmaker()
    async with sm() as session:
        total_de = (
            await session.execute(
                select(func.count()).select_from(Deal).where(Deal.juridiction == "DE")
            )
        ).scalar_one()

        stmt = (
            select(Deal)
            .where(
                Deal.juridiction == "DE",
                or_(
                    Deal.offer_price.is_(None),
                    Deal.offer_price < LOW_THRESHOLD,
                    Deal.offer_price > HIGH_THRESHOLD,
                ),
            )
            .order_by(Deal.announcement_date.desc())
        )
        deals = (await session.execute(stmt)).scalars().all()

        for deal in deals:
            bucket = _bucket(deal.offer_price)
            counts[bucket] = counts.get(bucket, 0) + 1
            premarket = await _premarket_price(session, deal)
            rows.append(
                {
                    "deal_id": deal.id,
                    "regulator_ref": deal.regulator_ref,
                    "target_company": deal.target_name,
                    "offer_price": deal.offer_price,
                    "currency": deal.currency or "",
                    "premarket_price": premarket if premarket is not None else "",
                    "bucket": bucket,
                    "announcement_date": deal.announcement_date.isoformat(),
                    "source_pdf_url": deal.source_url or "",
                    "pdf_path": deal.pdf_path or "",
                }
            )

    await dispose_engine()
    _write_csv(rows)
    _print_summary(total_de, counts, len(rows))


if __name__ == "__main__":
    asyncio.run(_audit())
