"""Phase 6 Step 0 — export every deal to a CSV for manual labelling.

The operator (Baptiste) reads each row, checks the deal outcome via
Boursorama / Borsa Italiana / Reuters / official regulator pages, then
fills the `label_y` column:

    label_y = 1   → completed (settlement done, squeeze-out closed,
                    delisting effective)
    label_y = 0   → failed   (withdrawal, regulator block, acceptance
                    threshold missed, lapsed offer)
    label_y blank → still pending (will be predicted at inference time,
                    NOT used for training)

Once the labelled CSV is back, Phase 6 Step 1 (migration 0008) adds the
`completion_label` columns to `deals` and `scripts/import_labels.py`
loads them.

Run:
    python scripts/export_deals_for_labelling.py [output_path]

Default output: `artifacts/phase-06/deals_to_label.csv`.

Columns emitted (operator-facing):
    id, juridiction, regulator_ref, target_name, acquirer_name,
    deal_type, status (auto-inferred from ingestion), announcement_date,
    expected_close_date, days_open (today - announcement), offer_price,
    currency, ticker_target, events_count, source_url,
    label_y (empty), label_source (empty), label_notes (empty)
"""

from __future__ import annotations

import asyncio
import csv
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.db import get_engine
from src.core.models import Deal, Event

_CSV_HEADER = [
    "id",
    "juridiction",
    "regulator_ref",
    "target_name",
    "acquirer_name",
    "deal_type",
    "status",
    "announcement_date",
    "expected_close_date",
    "days_open",
    "offer_price",
    "currency",
    "ticker_target",
    "events_count",
    "source_url",
    # ---- operator fills these ----
    "label_y",
    "label_source",
    "label_notes",
]


async def collect_rows() -> list[dict[str, Any]]:
    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    today = date.today()

    async with sf() as session:
        # Pull deals + per-deal event count in one round-trip.
        deal_rows = (
            await session.execute(
                select(
                    Deal,
                    func.count(Event.id).label("events_count"),
                )
                .outerjoin(Event, Event.deal_id == Deal.id)
                .group_by(Deal.id)
                .order_by(Deal.juridiction, Deal.announcement_date.desc())
            )
        ).all()

    rows: list[dict[str, Any]] = []
    for deal, events_count in deal_rows:
        days_open = (today - deal.announcement_date).days if deal.announcement_date else None
        rows.append(
            {
                "id": deal.id,
                "juridiction": deal.juridiction,
                "regulator_ref": deal.regulator_ref,
                "target_name": deal.target_name,
                "acquirer_name": deal.acquirer_name,
                "deal_type": deal.deal_type,
                "status": deal.status,
                "announcement_date": deal.announcement_date.isoformat()
                if deal.announcement_date
                else "",
                "expected_close_date": deal.expected_close_date.isoformat()
                if deal.expected_close_date
                else "",
                "days_open": days_open if days_open is not None else "",
                "offer_price": str(deal.offer_price) if deal.offer_price is not None else "",
                "currency": deal.currency or "",
                "ticker_target": deal.ticker_target or "",
                "events_count": events_count,
                "source_url": deal.source_url or "",
                # Operator-fillable columns left blank.
                "label_y": "",
                "label_source": "",
                "label_notes": "",
            }
        )
    return rows


async def main(output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = await collect_rows()

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_HEADER, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    # Summary so the operator immediately sees what they're labelling.
    by_jurisdiction: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for r in rows:
        by_jurisdiction[r["juridiction"]] = by_jurisdiction.get(r["juridiction"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    print(f"Wrote {len(rows)} deals to {output_path}")
    print(f"  By jurisdiction: {by_jurisdiction}")
    print(f"  By status      : {by_status}")
    print(f"  Generated at   : {datetime.now(tz=UTC).isoformat()}")
    return 0


if __name__ == "__main__":
    default_path = Path("artifacts/phase-06/deals_to_label.csv")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    sys.exit(asyncio.run(main(out)))
