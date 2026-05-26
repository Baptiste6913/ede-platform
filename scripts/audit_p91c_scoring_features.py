"""Phase 9.1c-[G-2] — audit the Phase-6 scoring feature consumption.

Reads what `src.scoring.features.extract_cluster_features` actually pulls
from the `deals` table, joins it against the labelled universe
(``completion_label IS NOT NULL``), and reports per-jurisdiction populated
counts for each ingredient. The goal is to confirm — empirically, on the
live DB state — that the P9.1c pricing work (offer_price /
offer_price_total_eur / pricing_source / offer_price_quality_flag) does NOT
intersect the scoring feature set, hence the [G] re-fit can only be a token
non-regression check.

Outputs:
  - data/audits/p91c_scoring_features_audit.csv
  - a console summary table

Run (PowerShell, repo root, postgres up):
  $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/audit_p91c_scoring_features.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "data" / "audits" / "p91c_scoring_features_audit.csv"

# Ingredients consumed by `extract_cluster_features` (src/scoring/features.py).
# Each tuple = (deal-column-name, label-for-CSV, contributes-to-feature(s)).
INGREDIENTS: tuple[tuple[str, str, str], ...] = (
    ("premium_pct", "premium_pct", "bid_premium_pct"),
    ("min_acceptance_threshold", "min_acceptance_threshold", "min_acceptance_threshold"),
    ("expected_close_date", "expected_close_date", "days_to_expected_close"),
    ("deal_type", "deal_type", "deal_type + payment_type"),
    (
        "acquirer_name",
        "acquirer_name (non-pending)",
        "acquirer_type + cross_border + fdi_risk_flag",
    ),
)

# Columns that P9.1c populated but features.py does NOT consume.
P91C_NON_CONSUMED: tuple[str, ...] = (
    "offer_price",
    "offer_price_total_eur",
    "offer_price_quality_flag",
    "pricing_source",
)


FIELDNAMES = [
    "jurisdiction",
    "labelled_clusters",
    "ingredient",
    "feeds_feature",
    "populated_clusters",
    "populated_pct",
]


async def _audit() -> None:
    sm = get_sessionmaker()
    rows: list[dict[str, object]] = []
    async with sm() as session:
        # Cluster = distinct (target_name, juridiction) among labelled deals.
        cluster_rows = (
            await session.execute(
                select(Deal.target_name, Deal.juridiction)
                .where(Deal.completion_label.is_not(None))
                .where(Deal.target_name != "[pending parse]")
                .distinct()
            )
        ).all()

        # Group clusters by jurisdiction for the report header.
        per_jur: dict[str, list[tuple[str, str]]] = {}
        for target, jur in cluster_rows:
            per_jur.setdefault(jur, []).append((target, jur))

        for jur in sorted(per_jur):
            cluster_keys = per_jur[jur]
            total = len(cluster_keys)
            for col, label, feat in INGREDIENTS:
                populated = 0
                for target, _ in cluster_keys:
                    stmt = select(func.count()).where(
                        Deal.target_name == target,
                        Deal.juridiction == jur,
                        Deal.completion_label.is_not(None),
                    )
                    if col == "acquirer_name":
                        stmt = stmt.where(
                            getattr(Deal, col).is_not(None),
                            getattr(Deal, col) != "[pending parse]",
                        )
                    else:
                        stmt = stmt.where(getattr(Deal, col).is_not(None))
                    cnt = (await session.execute(stmt)).scalar_one()
                    if cnt > 0:
                        populated += 1
                pct = (populated / total) * 100 if total else 0.0
                rows.append(
                    {
                        "jurisdiction": jur,
                        "labelled_clusters": total,
                        "ingredient": label,
                        "feeds_feature": feat,
                        "populated_clusters": populated,
                        "populated_pct": f"{pct:.1f}",
                    }
                )

        # P9.1c-touched columns: confirm population on labelled set + flag they
        # do NOT feed any scoring feature.
        for col in P91C_NON_CONSUMED:
            stmt_total = select(func.count()).where(Deal.completion_label.is_not(None))
            stmt_pop = stmt_total.where(getattr(Deal, col).is_not(None))
            tot = (await session.execute(stmt_total)).scalar_one()
            pop = (await session.execute(stmt_pop)).scalar_one()
            rows.append(
                {
                    "jurisdiction": "ALL",
                    "labelled_clusters": tot,
                    "ingredient": col,
                    "feeds_feature": "(NOT CONSUMED by features.py)",
                    "populated_clusters": pop,
                    "populated_pct": f"{(pop / tot) * 100:.1f}" if tot else "0.0",
                }
            )

    await dispose_engine()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    _print_summary(rows)


def _print_summary(rows: list[dict[str, object]]) -> None:
    print("=" * 78)
    print("P9.1c-[G-2] — Phase-6 scoring feature audit (labelled clusters)")
    print("=" * 78)
    header = f"{'jur':<5} {'clusters':>9} {'ingredient':<32} {'pop':>5} {'%':>6}"
    print(header)
    print("-" * 78)
    for r in rows:
        print(
            f"{r['jurisdiction']!s:<5} "
            f"{int(r['labelled_clusters']):>9} "
            f"{r['ingredient']!s:<32} "
            f"{int(r['populated_clusters']):>5} "
            f"{r['populated_pct']!s:>5}%"
        )
    print(f"\nCSV: {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(_audit())
