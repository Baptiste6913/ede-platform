"""Backfill P9.1a — re-parse misparsed BaFin offer_price outliers.

Targets BaFin (DE) deals the Step-0 audit flagged (offer_price < 5, > 500, or
NULL) that have not yet been re-parsed (`parser_version < PARSER_VERSION`).
For each, re-runs the fixed PDF parser and updates offer_price +
offer_price_quality_flag + parser_version. Transactional per deal and
idempotent: a second run finds nothing (parser_version is already current).

Scores of deals whose price was corrected or nulled are deleted (same
transaction) so Phase 6 can re-score on the fixed price — the actual re-score
is P9.1b, this only invalidates the stale scores.

`deals.pdf_path` stores the in-container path ("/repo/data/..."); it is remapped
to the local working tree before parsing.

Outputs data/audits/p91a_backfill_results.csv.

Run (PowerShell, repo root, postgres up):
  $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/backfill_p91a.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
from decimal import Decimal
from pathlib import Path

# Standalone invocation: make `src` importable before the first-party imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, or_, select

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal, Score
from src.ingestion.bafin.parser import PARSER_VERSION, extract_pdf_metadata

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "data" / "audits" / "p91a_backfill_results.csv"

LOW_THRESHOLD = Decimal("5")
HIGH_THRESHOLD = Decimal("500")

FIELDNAMES = [
    "deal_id",
    "regulator_ref",
    "target_company",
    "old_price",
    "new_price",
    "new_flag",
    "action",
    "scores_deleted",
]


def _local_pdf(pdf_path: str | None) -> Path | None:
    """Map a stored pdf_path to the local working tree, or None if unusable."""
    if not pdf_path:
        return None
    rel = pdf_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


def _classify(old: Decimal | None, new: Decimal | None) -> str:
    if new is None:
        return "nulled" if old is not None else "unchanged"
    if old is None or new != old:
        return "corrected"
    return "unchanged"


async def _backfill() -> None:
    rows: list[dict[str, object]] = []
    sm = get_sessionmaker()
    async with sm() as session:
        stmt = (
            select(Deal)
            .where(
                Deal.juridiction == "DE",
                Deal.parser_version < PARSER_VERSION,
                or_(
                    Deal.offer_price.is_(None),
                    Deal.offer_price < LOW_THRESHOLD,
                    Deal.offer_price > HIGH_THRESHOLD,
                ),
            )
            .order_by(Deal.id)
        )
        deals = (await session.execute(stmt)).scalars().all()

        for deal in deals:
            old_price = deal.offer_price
            local = _local_pdf(deal.pdf_path)
            if local is None:
                # Can't re-parse without the PDF — leave the row untouched.
                rows.append(
                    _row(
                        deal,
                        old_price,
                        old_price,
                        deal.offer_price_quality_flag,
                        "skipped_no_pdf",
                        0,
                    )
                )
                continue

            md = extract_pdf_metadata(local)
            new_price = md.offer_price
            new_flag = md.offer_price_quality_flag
            action = _classify(old_price, new_price)

            scores_deleted = 0
            if action in ("corrected", "nulled"):
                scores_deleted = (
                    await session.execute(
                        select(func.count()).select_from(Score).where(Score.deal_id == deal.id)
                    )
                ).scalar_one()
                await session.execute(delete(Score).where(Score.deal_id == deal.id))

            deal.offer_price = new_price
            deal.offer_price_quality_flag = new_flag
            deal.parser_version = PARSER_VERSION
            await session.commit()  # transactional per deal

            rows.append(_row(deal, old_price, new_price, new_flag, action, scores_deleted))

    await dispose_engine()
    _write_csv(rows)
    _print_summary(rows)


def _row(
    deal: Deal,
    old_price: Decimal | None,
    new_price: Decimal | None,
    new_flag: str,
    action: str,
    scores_deleted: int,
) -> dict[str, object]:
    return {
        "deal_id": deal.id,
        "regulator_ref": deal.regulator_ref,
        "target_company": deal.target_name,
        "old_price": old_price if old_price is not None else "",
        "new_price": new_price if new_price is not None else "",
        "new_flag": new_flag,
        "action": action,
        "scores_deleted": scores_deleted,
    }


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(rows: list[dict[str, object]]) -> None:
    by_action: dict[str, int] = {}
    scores_total = 0
    for r in rows:
        by_action[str(r["action"])] = by_action.get(str(r["action"]), 0) + 1
        scores_total += int(r["scores_deleted"])
    print("=" * 60)
    print("P9.1a backfill — BaFin offer_price re-parse")
    print("=" * 60)
    print(f"deals processed : {len(rows)}")
    for action in sorted(by_action):
        print(f"  {action:<16}: {by_action[action]}")
    print(f"scores deleted  : {scores_total}")
    print(f"CSV: {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(_backfill())
