"""P9.2 02d — Consob flag promotion.

Categorizes the 47 Consob (IT) deals into 4 target
`offer_price_quality_flag` buckets via a first-match rule:

  1. OUTLIER        → failed_validation (offer_price NOT NULL AND
                                         price ∉ [0.01, 10 000])
  2. MIXED          → suspect_mixed     (deal_type = 'opas')
  3. MANUAL_REVIEW  → manual_review     (offer_price IS NULL OR
                                         target_name = '[pending parse]')
  4. PROMOTABLE     → verified_cash     (else)

OUTLIER runs before MIXED so that Banco BPM (id 1034: deal_type=opas,
offer_price=3.828 B EUR — controvalore complessivo mis-parsed as
unit price) lands in `failed_validation` rather than propagating the
broken value into 02e's mixed cash+share split. The non-NULL guard
on OUTLIER lets NULL-priced OPAS deals (Mediobanca, Banca Pop
Sondrio) fall through to MIXED as intended.

PROMOTABLE deals receive a `statistical_outlier` audit-trail bit
(`offer_price > 107.19`) which is informational only — it does not
hold back the promotion. Health Italia (id 334, 300 €) is the only
current hit on the 47-deal corpus.

`parser_version` bumps to 2 on every re-categorized row (mirror of
P9.1a). Transactional per deal, idempotent (re-running finds
nothing since the new flag is already current).

Default mode is dry-run (writes CSV, no DB UPDATE). Pass --apply to
execute the UPDATEs. The companion `scripts/promote_consob_flags_02d_invalidate_scores.py`
will handle Score row invalidation in a separate step, per P9.1a
convention.

Run (PowerShell, repo root, postgres up):
  $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/promote_consob_flags_02d.py
  .venv/Scripts/python.exe scripts/promote_consob_flags_02d.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "data" / "audits" / "p92_02d_promotion_results.csv"

PARSER_VERSION_02D = 2

PRICE_LOWER = Decimal("0.01")
PRICE_UPPER = Decimal("10000")
OUTLIER_TRACE_THRESHOLD = Decimal("107.19")  # p95 × 3 of the live IT corpus

PENDING_PARSE_MARKER = "[pending parse]"

FIELDNAMES = [
    "deal_id",
    "target_name",
    "regulator_ref",
    "offer_price",
    "deal_type",
    "old_flag",
    "new_flag",
    "statistical_outlier",
    "action",
]


@dataclass(frozen=True, slots=True)
class DealView:
    """Subset of Deal fields the categorizer reads. Lets unit tests
    cover the logic without touching the ORM / DB."""

    deal_type: str
    offer_price: Decimal | None
    target_name: str


def categorize(deal: DealView) -> tuple[str, bool]:
    """First-match categorization → (new_flag, statistical_outlier).

    `statistical_outlier` is only ever True on the PROMOTABLE path.
    """
    # 1. OUTLIER — non-NULL price outside the validated envelope.
    #    Runs before MIXED so Banco BPM (opas + 3.8 B EUR controvalore-as-
    #    unit-price bug) lands in failed_validation rather than
    #    propagating into 02e. The non-NULL guard lets OPAS rows with
    #    NULL price fall through to MIXED unaffected.
    if deal.offer_price is not None and (
        deal.offer_price < PRICE_LOWER or deal.offer_price > PRICE_UPPER
    ):
        return "failed_validation", False

    # 2. MIXED — OPAS routes to suspect_mixed regardless of NULL/in-bounds.
    #    Resolved in 02e (Banca Sistema-class cash + share split).
    if deal.deal_type == "opas":
        return "suspect_mixed", False

    # 3. MANUAL_REVIEW — NULL price (extraction failed) OR upstream
    #    partial-ingestion marker (target_name still '[pending parse]').
    if deal.offer_price is None or deal.target_name == PENDING_PARSE_MARKER:
        return "manual_review", False

    # 4. PROMOTABLE — cash, in bounds. Trace high prices for audit.
    statistical_outlier = deal.offer_price > OUTLIER_TRACE_THRESHOLD
    return "verified_cash", statistical_outlier


async def _promote(*, apply: bool) -> None:
    rows: list[dict[str, object]] = []
    sm = get_sessionmaker()
    async with sm() as session:
        stmt = select(Deal).where(Deal.juridiction == "IT").order_by(Deal.id)
        deals = (await session.execute(stmt)).scalars().all()

        for deal in deals:
            view = DealView(
                deal_type=deal.deal_type,
                offer_price=deal.offer_price,
                target_name=deal.target_name,
            )
            new_flag, stat_outlier = categorize(view)
            old_flag = deal.offer_price_quality_flag

            if new_flag == old_flag and deal.parser_version >= PARSER_VERSION_02D:
                action = "noop"
            elif apply:
                deal.offer_price_quality_flag = new_flag
                deal.parser_version = PARSER_VERSION_02D
                await session.commit()
                action = "applied"
            else:
                action = "would_apply"

            rows.append(
                {
                    "deal_id": deal.id,
                    "target_name": deal.target_name,
                    "regulator_ref": deal.regulator_ref,
                    "offer_price": deal.offer_price if deal.offer_price is not None else "",
                    "deal_type": deal.deal_type,
                    "old_flag": old_flag,
                    "new_flag": new_flag,
                    "statistical_outlier": stat_outlier,
                    "action": action,
                }
            )

    await dispose_engine()
    _write_csv(rows)
    _print_summary(rows, apply=apply)


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(rows: list[dict[str, object]], *, apply: bool) -> None:
    by_new_flag: dict[str, int] = {}
    by_action: dict[str, int] = {}
    stat_outliers = 0
    for r in rows:
        by_new_flag[str(r["new_flag"])] = by_new_flag.get(str(r["new_flag"]), 0) + 1
        by_action[str(r["action"])] = by_action.get(str(r["action"]), 0) + 1
        if r["statistical_outlier"]:
            stat_outliers += 1

    mode = "APPLY" if apply else "DRY-RUN"
    print("=" * 60)
    print(f"P9.2 02d Consob flag promotion -- {mode}")
    print("=" * 60)
    print(f"deals processed       : {len(rows)}")
    print("by target flag:")
    for flag in sorted(by_new_flag):
        print(f"  {flag:<24}: {by_new_flag[flag]}")
    print("by action:")
    for action in sorted(by_action):
        print(f"  {action:<24}: {by_action[action]}")
    print(f"statistical_outlier=True: {stat_outliers}")
    print(f"CSV: {OUTPUT}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute UPDATEs. Default is dry-run (CSV only, no DB write).",
    )
    args = parser.parse_args()
    asyncio.run(_promote(apply=args.apply))


if __name__ == "__main__":
    main()
