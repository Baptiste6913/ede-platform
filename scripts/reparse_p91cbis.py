"""Phase 9.1c-bis — re-parse non-outlier BaFin deals (parser_version=1 → 2).

The P9.1a backfill targeted only the 17 audit outliers (offer_price < 5, > 500,
or NULL); the 25 non-outlier DE deals were never re-parsed and still carry
``parser_version = 1`` + the migration-default ``suspect_low_unverified`` flag.
This closes that data-hygiene gap before the Phase-6 re-scoring at [G].

For each target deal:

  1. Re-parse the PDF via the (P9.1a-fixed) parser.
  2. Compute the action — promoted (flag suspect_low → verified_cash), unchanged
     (no new clause found), new_suspect_mixed (unexpected — would mean an
     un-flagged mixed offer hiding in the non-outliers), or price_changed
     (offer_price moved > 1% — invalidate the deal's scores).
  3. UPDATE offer_price / offer_price_quality_flag / parser_version=2 in one
     transaction. If price_changed, DELETE FROM scores in the same tx.

Idempotent: a re-run finds zero parser_version=1 deals once this completes.

Outputs ``data/audits/p91cbis_reparse_results.csv``.
"""

from __future__ import annotations

import asyncio
import csv
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal, Score
from src.ingestion.bafin.parser import PARSER_VERSION, extract_pdf_metadata

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "data" / "audits" / "p91cbis_reparse_results.csv"

PRICE_CHANGE_THRESHOLD = Decimal("0.01")  # 1% — beyond this, invalidate scores

FIELDNAMES = [
    "deal_id",
    "target",
    "old_offer_price",
    "new_offer_price",
    "old_flag",
    "new_flag",
    "parser_version_old",
    "parser_version_new",
    "action",
    "offer_price_changed_pct",
    "scores_deleted",
]


def _local_pdf(pdf_path: str | None) -> Path | None:
    if not pdf_path:
        return None
    rel = pdf_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


def _classify(
    old_price: Decimal | None,
    new_price: Decimal | None,
    old_flag: str,
    new_flag: str,
) -> tuple[str, Decimal | None]:
    """Return (action, price_change_pct_or_none)."""
    if new_flag == "suspect_mixed":
        return ("new_suspect_mixed", None)
    if new_price is None:
        # Parser found no clean cash clause — flag stays suspect_low_unverified.
        return ("unchanged", None)
    # We have a new cash price; compute the delta vs the old (parser-v1) value.
    if old_price is None or old_price == 0:
        # No usable baseline — flag promotion only, treat as promoted.
        return ("promoted", None)
    delta_pct = abs(new_price - old_price) / old_price
    if delta_pct > PRICE_CHANGE_THRESHOLD:
        return ("price_changed", delta_pct)
    # Same price, just a flag promotion (suspect_low → verified_cash).
    if old_flag != new_flag:
        return ("promoted", delta_pct)
    return ("unchanged", delta_pct)


async def _reparse() -> None:
    rows: list[dict[str, object]] = []
    sm = get_sessionmaker()
    async with sm() as session:
        stmt = (
            select(Deal)
            .where(Deal.juridiction == "DE", Deal.parser_version < PARSER_VERSION)
            .order_by(Deal.id)
        )
        deals = (await session.execute(stmt)).scalars().all()

        for deal in deals:
            old_price = deal.offer_price
            old_flag = deal.offer_price_quality_flag
            local = _local_pdf(deal.pdf_path)
            if local is None:
                rows.append(
                    _row(
                        deal,
                        old_price,
                        old_price,
                        old_flag,
                        old_flag,
                        deal.parser_version,
                        deal.parser_version,
                        "skipped_no_pdf",
                        None,
                        0,
                    )
                )
                continue

            md = extract_pdf_metadata(local)
            new_price = md.offer_price
            new_flag = md.offer_price_quality_flag
            action, delta_pct = _classify(old_price, new_price, old_flag, new_flag)

            scores_deleted = 0
            if action == "price_changed":
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

            rows.append(
                _row(
                    deal,
                    old_price,
                    new_price,
                    old_flag,
                    new_flag,
                    1,
                    PARSER_VERSION,
                    action,
                    delta_pct,
                    scores_deleted,
                )
            )

    await dispose_engine()
    _write_csv(rows)
    _print_summary(rows)


def _row(
    deal: Deal,
    old_price: Decimal | None,
    new_price: Decimal | None,
    old_flag: str,
    new_flag: str,
    pv_old: int,
    pv_new: int,
    action: str,
    delta_pct: Decimal | None,
    scores_deleted: int,
) -> dict[str, object]:
    return {
        "deal_id": deal.id,
        "target": deal.target_name,
        "old_offer_price": old_price if old_price is not None else "",
        "new_offer_price": new_price if new_price is not None else "",
        "old_flag": old_flag,
        "new_flag": new_flag,
        "parser_version_old": pv_old,
        "parser_version_new": pv_new,
        "action": action,
        "offer_price_changed_pct": (f"{delta_pct * 100:.3f}" if delta_pct is not None else ""),
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
    print("=" * 70)
    print("P9.1c-bis — non-outlier BaFin re-parse (parser_version 1 -> 2)")
    print("=" * 70)
    print(f"deals processed : {len(rows)}")
    for action in sorted(by_action):
        print(f"  {action:<22}: {by_action[action]}")
    print(f"scores deleted  : {scores_total}")
    print(f"CSV: {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(_reparse())
