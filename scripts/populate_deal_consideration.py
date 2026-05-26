"""Phase 9.1c — populate deal_consideration for suspect_mixed BaFin deals.

For each deal flagged ``suspect_mixed`` by the P9.1a parser (Commerzbank,
ProSieben in the current corpus), re-parses the stored PDF to recover the
cash + share legs and the acquirer name, resolves the acquirer to its
canonical ISIN / yfinance ticker via :mod:`src.pricing.acquirer_registry`,
and upserts a row in ``deal_consideration``. Idempotent (PK on ``deal_id``,
upsert via ``session.merge``).

An unknown acquirer raises — at V1 there are exactly two known cases, so a
miss is a real bug to investigate, not a row to skip silently.

Outputs ``data/audits/p91c_consideration_populated.csv`` (deal_id, target,
cash_eur, share_ratio, acquirer_ticker, source_clause_excerpt).

Run (PowerShell, postgres up):
  $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/populate_deal_consideration.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal, DealConsideration
from src.ingestion.bafin.parser import _extract_consideration, _read_pdf_text
from src.pricing.acquirer_registry import resolve_acquirer

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "data" / "audits" / "p91c_consideration_populated.csv"

FIELDNAMES = [
    "deal_id",
    "target",
    "cash_eur",
    "share_ratio",
    "acquirer_ticker",
    "acquirer_isin",
    "source_clause_excerpt",
]


def _local_pdf(pdf_path: str | None) -> Path | None:
    if not pdf_path:
        return None
    rel = pdf_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


async def _populate() -> None:
    rows: list[dict[str, object]] = []
    sm = get_sessionmaker()
    async with sm() as session:
        stmt = (
            select(Deal).where(Deal.offer_price_quality_flag == "suspect_mixed").order_by(Deal.id)
        )
        deals = (await session.execute(stmt)).scalars().all()

        for deal in deals:
            local = _local_pdf(deal.pdf_path)
            if local is None:
                raise RuntimeError(
                    f"deal {deal.id} ({deal.target_name}): missing local PDF "
                    f"({deal.pdf_path!r}) — cannot re-parse for consideration."
                )
            text = _read_pdf_text(local, max_pages=10)
            struct = _extract_consideration(text)
            if struct is None:
                raise RuntimeError(
                    f"deal {deal.id} ({deal.target_name}): _extract_consideration "
                    "returned None on a suspect_mixed deal — parser regression."
                )
            if struct.acquirer_name_raw is None:
                raise RuntimeError(f"deal {deal.id}: empty acquirer name from parser.")
            acquirer = resolve_acquirer(struct.acquirer_name_raw)
            if acquirer is None:
                raise RuntimeError(
                    f"deal {deal.id} ({deal.target_name}): unknown acquirer "
                    f"{struct.acquirer_name_raw!r} — add it to acquirer_registry."
                )

            row = DealConsideration(
                deal_id=deal.id,
                cash_eur=struct.cash_eur,
                share_ratio=struct.share_ratio,
                acquirer_isin=acquirer.isin,
                acquirer_ticker_yf=acquirer.ticker_yf,
                source_clause_excerpt=struct.source_excerpt,
            )
            await session.merge(row)  # upsert on deal_id
            await session.commit()

            rows.append(
                {
                    "deal_id": deal.id,
                    "target": deal.target_name,
                    "cash_eur": struct.cash_eur if struct.cash_eur is not None else "",
                    "share_ratio": struct.share_ratio,
                    "acquirer_ticker": acquirer.ticker_yf,
                    "acquirer_isin": acquirer.isin,
                    "source_clause_excerpt": struct.source_excerpt,
                }
            )

    await dispose_engine()
    _write_csv(rows)
    _print_summary(rows)


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(rows: list[dict[str, object]]) -> None:
    print("=" * 60)
    print("P9.1c — deal_consideration populated")
    print("=" * 60)
    for r in rows:
        cash = r["cash_eur"] if r["cash_eur"] != "" else "—"
        print(
            f"  deal {r['deal_id']} {str(r['target'])[:30]:<30} "
            f"cash={cash:<6} share={r['share_ratio']} x {r['acquirer_ticker']}"
        )
    print(f"CSV: {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(_populate())
