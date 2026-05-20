"""Import `artifacts/phase-06/deals_labelled.csv` into `deals.completion_label`.

Handles FR multi-stage cluster IDs (`13_10_3_2`) by applying the same
label to every underlying `deals.id` in the cluster. Idempotent: a
re-run overwrites the existing label + source + date for matching
deals.

Output: artifacts/phase-06/import-labels-summary.json.
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.db import get_engine
from src.core.models import Deal


def _parse_label(raw: str) -> int | None:
    raw = raw.strip()
    if raw == "1":
        return 1
    if raw == "0":
        return 0
    return None


def _parse_cluster_ids(id_cluster: str) -> list[int]:
    """`'13_10_3_2'` -> [13, 10, 3, 2]; `'348'` -> [348]."""
    return [int(p) for p in id_cluster.split("_") if p.strip().isdigit()]


async def main(csv_path: Path, output_summary: Path) -> int:
    rows: list[dict[str, str]] = []
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"error: {csv_path} is empty", file=sys.stderr)
        return 2

    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(tz=UTC)

    applied_labels = 0
    skipped_no_label = 0
    missing_deal_ids: list[int] = []
    label_dist: dict[str, int] = {"0": 0, "1": 0, "null": 0}

    async with sf() as session:
        for row in rows:
            label = _parse_label(row.get("label_y", ""))
            source = row.get("label_source", "").strip()
            notes = row.get("label_notes", "").strip()

            if label is None:
                skipped_no_label += 1
                label_dist["null"] += 1
                continue
            label_dist[str(label)] += 1

            deal_ids = _parse_cluster_ids(row["id_cluster"])
            for did in deal_ids:
                deal = await session.get(Deal, did)
                if deal is None:
                    missing_deal_ids.append(did)
                    continue
                deal.completion_label = label
                deal.completion_label_source = source or None
                deal.completion_label_date = now
                if notes:
                    # Mirror notes into the source field if no URL was given,
                    # otherwise append as suffix so we don't lose context.
                    if source:
                        deal.completion_label_source = f"{source} | {notes}"
                    else:
                        deal.completion_label_source = notes
                applied_labels += 1
        await session.commit()

        labelled = await session.scalar(
            select(Deal).where(Deal.completion_label.is_not(None)).limit(1)
        )
        _ = labelled
        labelled_count = await session.scalar(
            select(__import__("sqlalchemy").func.count(Deal.id)).where(
                Deal.completion_label.is_not(None)
            )
        )

    summary: dict[str, Any] = {
        "executed_at_utc": now.isoformat(),
        "csv_path": str(csv_path),
        "csv_rows": len(rows),
        "applied_labels_total_deals": applied_labels,
        "skipped_no_label_rows": skipped_no_label,
        "missing_deal_ids": missing_deal_ids,
        "labelled_deals_in_db_after_run": labelled_count,
        "label_distribution_from_csv": label_dist,
    }
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_summary.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    csv_default = Path("artifacts/phase-06/deals_labelled.csv")
    summary_default = Path("artifacts/phase-06/import-labels-summary.json")
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else csv_default
    summary_path = Path(sys.argv[2]) if len(sys.argv) > 2 else summary_default  # noqa: PLR2004
    sys.exit(asyncio.run(main(csv_path, summary_path)))
