"""Phase 6 Step-0 extension — collapse the 24-month dataset into a
labelling-friendly CSV (one row per unique deal, not per BDIF filing).

Algorithm (per Decision #2 from the user):

1. **Filter** every deal with `announcement_date >= 2024-05-20`.
2. **FR collapse** — multi-stage BDIF filings are sub-stages of one
   underlying OPA. Cluster by `(target_name, juridiction='FR')` with a
   chronological gap of <730 days between consecutive filings to keep a
   chain together. Each cluster becomes one row. `[pending parse]`
   targets stay as singletons (no reliable cluster key).
3. **IT / DE pass-through** — keep one row per `deals` row (already 1
   deal per row, no multi-stage chain in Consob/BaFin discovery).
4. **Pre-fill rules**:
   - `candidate_failure_flag = 'Y'` for entries matching the SQL
     candidate-failure shortlist (see
     `artifacts/phase-06/candidate-failures-from-extension.md`).
   - `label_y = '1'` if `events_count >= 4` (long FR chains are
     overwhelmingly closed deals).
   - `label_y` blank otherwise.

Output: `artifacts/phase-06/deals_to_label_24mo_collapsed.csv`.
"""

from __future__ import annotations

import asyncio
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.db import get_engine
from src.core.models import Deal

_SINCE = date(2024, 5, 20)
_CLUSTER_GAP_DAYS = 730  # 24 months
_AUTO_LABEL_1_THRESHOLD = 4  # collapsed events_count >= 4 -> likely closed

# Pre-fill `candidate_failure_flag=Y` for these (target_name, jurisdiction)
# pairs. See artifacts/phase-06/candidate-failures-from-extension.md.
_FAILURE_TARGETS: set[tuple[str, str]] = {
    # --- FR (9 from corrected Q1) ---
    ("FR", "COVIVIO HOTELS"),
    ("FR", "AUREA"),
    ("FR", "FUTUREN"),
    ("FR", "LE BELIER"),
    ("FR", "ETABLISSEMENTS FAUVET GIREL"),
    ("FR", "UNION FINANCIERE DE FRANCE BANQUE"),
    ("FR", "SOMFY SA"),
    ("FR", "ZODIAC AEROSPACE"),
    ("FR", "LISI"),
}

# Substring matches (case-insensitive) to flag IT/DE failures by name when
# the acquirer extraction left a `[pending parse]` placeholder.
_FAILURE_NAME_PATTERNS: tuple[tuple[str, str], ...] = (
    # (jurisdiction, lowercased substring)
    ("IT", "banco bpm"),  # UC withdrew on Banco BPM in July 2025
    ("DE", "prosiebensat.1"),  # PPF withdrew offer on ProSieben Q3 2025
)


_CSV_HEADER = [
    "id_cluster",
    "juridiction",
    "target_name",
    "acquirer_name",
    "deal_type",
    "earliest_announcement_date",
    "latest_event_date",
    "events_count",
    "expected_close_date",
    "offer_price",
    "currency",
    "candidate_failure_flag",
    "label_y",
    "label_source",
    "label_notes",
]


@dataclass
class ClusterRow:
    juridiction: str
    target_name: str
    acquirer_name: str
    deal_type: str
    earliest_announcement_date: date
    latest_event_date: date
    events_count: int
    expected_close_date: date | None
    offer_price: str
    currency: str
    deal_ids: list[int]


async def fetch_deals() -> list[Deal]:
    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        result = await session.execute(
            select(Deal)
            .where(Deal.announcement_date >= _SINCE)
            .order_by(Deal.juridiction, Deal.target_name, Deal.announcement_date)
        )
        return list(result.scalars().all())


def _best_acquirer(group: list[Deal]) -> str:
    """Pick the most informative acquirer label across a cluster."""
    for d in group:
        if d.acquirer_name and d.acquirer_name != "[pending parse]":
            return d.acquirer_name
    return group[0].acquirer_name


def _best_deal_type(group: list[Deal]) -> str:
    """First-stage deal_type captures the canonical operation; later
    stages tend to be `opr` / `opr_ro` (squeeze-out)."""
    return group[0].deal_type


def _best_expected_close(group: list[Deal]) -> date | None:
    candidates = [d.expected_close_date for d in group if d.expected_close_date]
    return max(candidates) if candidates else None


def _best_offer_price(group: list[Deal]) -> tuple[str, str]:
    for d in group:
        if d.offer_price is not None:
            return (str(d.offer_price), d.currency or "")
    return ("", "")


def collapse_fr(deals: list[Deal]) -> list[ClusterRow]:
    """Cluster FR deals by (target, gap<730d) — produce one row per cluster."""
    clusters: list[ClusterRow] = []
    by_target: dict[str, list[Deal]] = defaultdict(list)
    for d in deals:
        by_target[d.target_name].append(d)

    for target, group in by_target.items():
        if target == "[pending parse]":
            # Cannot cluster reliably — keep each as a singleton.
            for d in group:
                clusters.append(_singleton(d))
            continue

        group.sort(key=lambda d: d.announcement_date)
        current = [group[0]]
        for d in group[1:]:
            gap = (d.announcement_date - current[-1].announcement_date).days
            if gap < _CLUSTER_GAP_DAYS:
                current.append(d)
            else:
                clusters.append(_finalize_cluster(current))
                current = [d]
        clusters.append(_finalize_cluster(current))
    return clusters


def _finalize_cluster(group: list[Deal]) -> ClusterRow:
    price, currency = _best_offer_price(group)
    return ClusterRow(
        juridiction=group[0].juridiction,
        target_name=group[0].target_name,
        acquirer_name=_best_acquirer(group),
        deal_type=_best_deal_type(group),
        earliest_announcement_date=group[0].announcement_date,
        latest_event_date=group[-1].announcement_date,
        events_count=len(group),
        expected_close_date=_best_expected_close(group),
        offer_price=price,
        currency=currency,
        deal_ids=[d.id for d in group],
    )


def _singleton(d: Deal) -> ClusterRow:
    return ClusterRow(
        juridiction=d.juridiction,
        target_name=d.target_name,
        acquirer_name=d.acquirer_name,
        deal_type=d.deal_type,
        earliest_announcement_date=d.announcement_date,
        latest_event_date=d.announcement_date,
        events_count=1,
        expected_close_date=d.expected_close_date,
        offer_price=str(d.offer_price) if d.offer_price is not None else "",
        currency=d.currency or "",
        deal_ids=[d.id],
    )


def passthrough(deals: list[Deal]) -> list[ClusterRow]:
    return [_singleton(d) for d in deals]


def _candidate_failure_flag(row: ClusterRow) -> str:
    if (row.juridiction, row.target_name) in _FAILURE_TARGETS:
        return "Y"
    target_lower = row.target_name.lower()
    for jur, substring in _FAILURE_NAME_PATTERNS:
        if jur == row.juridiction and substring in target_lower:
            return "Y"
    return ""


def _auto_label_y(row: ClusterRow) -> str:
    if row.events_count >= _AUTO_LABEL_1_THRESHOLD:
        return "1"
    return ""


def to_csv_row(row: ClusterRow) -> dict[str, Any]:
    return {
        "id_cluster": "_".join(str(i) for i in row.deal_ids),
        "juridiction": row.juridiction,
        "target_name": row.target_name,
        "acquirer_name": row.acquirer_name,
        "deal_type": row.deal_type,
        "earliest_announcement_date": row.earliest_announcement_date.isoformat(),
        "latest_event_date": row.latest_event_date.isoformat(),
        "events_count": row.events_count,
        "expected_close_date": (
            row.expected_close_date.isoformat() if row.expected_close_date else ""
        ),
        "offer_price": row.offer_price,
        "currency": row.currency,
        "candidate_failure_flag": _candidate_failure_flag(row),
        "label_y": _auto_label_y(row),
        "label_source": "",
        "label_notes": "",
    }


async def main(output_path: Path) -> int:
    deals = await fetch_deals()
    fr_deals = [d for d in deals if d.juridiction == "FR"]
    it_deals = [d for d in deals if d.juridiction == "IT"]
    de_deals = [d for d in deals if d.juridiction == "DE"]

    fr_clusters = collapse_fr(fr_deals)
    it_rows = passthrough(it_deals)
    de_rows = passthrough(de_deals)

    rows = fr_clusters + it_rows + de_rows
    rows.sort(
        key=lambda r: (r.juridiction, r.earliest_announcement_date),
        reverse=False,
    )
    rows.sort(key=lambda r: (r.juridiction, -r.earliest_announcement_date.toordinal()))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_HEADER, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for r in rows:
            writer.writerow(to_csv_row(r))

    # Summary
    by_jur: dict[str, int] = defaultdict(int)
    flagged: dict[str, int] = defaultdict(int)
    pre_labeled_1: dict[str, int] = defaultdict(int)
    for r in rows:
        by_jur[r.juridiction] += 1
        flag = _candidate_failure_flag(r)
        if flag == "Y":
            flagged[r.juridiction] += 1
        if _auto_label_y(r) == "1":
            pre_labeled_1[r.juridiction] += 1

    print(f"Wrote {len(rows)} collapsed rows to {output_path}")
    print(f"  By jurisdiction (rows): FR={by_jur['FR']} IT={by_jur['IT']} DE={by_jur['DE']}")
    print(
        "  candidate_failure_flag=Y: " f"FR={flagged['FR']} IT={flagged['IT']} DE={flagged['DE']}"
    )
    print(
        "  label_y=1 auto-filled    : "
        f"FR={pre_labeled_1['FR']} IT={pre_labeled_1['IT']} DE={pre_labeled_1['DE']}"
    )
    print(f"  FR input rows           : {len(fr_deals)} -> collapsed to {len(fr_clusters)}")
    return 0


if __name__ == "__main__":
    default_path = Path("artifacts/phase-06/deals_to_label_24mo_collapsed.csv")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    sys.exit(asyncio.run(main(out)))
