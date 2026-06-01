"""P9.2 02b Step 0 — stratified random sample of 596 FR verified_cash deals.

Pulls 12 random deals per announcement year (2022-2026) + 8 obligatory
study cases (FNAC DARTY x2, TRAVEL TECHNOLOGY INTERACTIVE x2, SERMA GROUP
x4) = 68 total. Random seed pinned so the sample is reproducible.

Excludes deals already manually verified in P9.2 02a Step 0 (TIPIAK,
PRODWARE, ALTUR, TARKETT, PCAS, CIFE, SQLI, OVH, GROUPE FLO, ESKER,
SOMFY, UNIBEL, POULAILLON, COGELEC, LV GROUP, MONCEY, LISI, VERALLIA,
SELECTIRENTE, FINANCIERE AGACHE, ARTOIS, BOUYGUES) so the 02b rate
estimate is not biased by the cases we already know about.

Writes ``data/audits/p92_02b_sample.csv``.
"""

from __future__ import annotations

import asyncio
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "data" / "audits" / "p92_02b_sample.csv"

SEED = 20260529
RANDOM_PER_YEAR = 12
YEARS = (2022, 2023, 2024, 2025, 2026)

# Already-verified targets from P9.2 02a Step 0 audits. Substring match so
# variants like "TARKETT S.A." vs "TARKETT" both excluded.
EXCLUDE_TARGET_LIKE = [
    "TIPIAK",
    "PRODWARE",
    "ALTUR",
    "TARKETT",
    "PCAS",
    "CIFE",
    "COMPAGNIE INDUSTRIELLE ET FINANCIERE",
    "SQLI",
    "OVH",
    "GROUPE FLO",
    "ESKER",
    "SOMFY",
    "UNIBEL",
    "POULAILLON",
    "COGELEC",
    "LV GROUP",
    "MONCEY",
    "LISI",
    "VERALLIA",
    "SELECTIRENTE",
    "FINANCIERE AGACHE",
    "SOCIETE INDUSTRIELLE",  # ARTOIS
    "BOUYGUES",
    # Obligatory cases handled separately — exclude from random pool.
    "SERMA GROUP",
    "FNAC DARTY",
    "TRAVEL TECHNOLOGY INTERACTIVE",
]

OBLIGATORY_REFS = (
    "226C0287",  # FNAC DARTY
    "226C0644",  # FNAC DARTY
    "224C0915",  # TRAVEL TECH
    "224C1289",  # TRAVEL TECH
    "218C1907",  # SERMA 229.19
    "218C2028",  # SERMA 229.19
    "222C2665",  # SERMA 430
    "223C0160",  # SERMA 430
)


async def _build_sample() -> None:
    engine = create_async_engine(get_settings().database_url, echo=False, future=True)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)

    rng = random.Random(SEED)  # noqa: S311 — sampling for audit reproducibility, not crypto
    rows: list[dict[str, object]] = []

    async with sm() as session:
        # Pull every verified_cash row + its announcement year + price + pdf_path.
        full = (
            await session.execute(
                text(
                    "SELECT id, regulator_ref, target_name, "
                    "EXTRACT(YEAR FROM announcement_date)::int AS year, "
                    "offer_price, pdf_path "
                    "FROM deals "
                    "WHERE juridiction='FR' "
                    "AND offer_price_quality_flag='verified_cash' "
                    "ORDER BY id"
                )
            )
        ).all()

        all_rows = [
            {
                "deal_id": r.id,
                "regulator_ref": r.regulator_ref,
                "target_name": r.target_name,
                "year": r.year,
                "offer_price": str(r.offer_price) if r.offer_price is not None else "",
                "pdf_path": r.pdf_path or "",
                "selection": "",
            }
            for r in full
        ]
    await engine.dispose()

    by_ref = {r["regulator_ref"]: r for r in all_rows}

    # 1. Obligatory study cases first.
    for ref in OBLIGATORY_REFS:
        row = by_ref.get(ref)
        if row is None:
            print(f"WARNING: obligatory ref {ref} not in verified_cash pool")
            continue
        clone = dict(row)
        clone["selection"] = "obligatory"
        rows.append(clone)

    obligatory_ids = {r["deal_id"] for r in rows}

    # 2. Random pool per year, filtering the excluded targets + obligatory ids.
    def _is_excluded(target: str) -> bool:
        upper = target.upper()
        return any(p in upper for p in EXCLUDE_TARGET_LIKE)

    for year in YEARS:
        pool = [
            r
            for r in all_rows
            if r["year"] == year
            and r["deal_id"] not in obligatory_ids
            and not _is_excluded(str(r["target_name"]))
        ]
        k = min(RANDOM_PER_YEAR, len(pool))
        picks = rng.sample(pool, k)
        for r in picks:
            clone = dict(r)
            clone["selection"] = f"random_{year}"
            rows.append(clone)
        print(f"year {year}: pool={len(pool)}, picked={k}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "deal_id",
                "regulator_ref",
                "target_name",
                "year",
                "offer_price",
                "pdf_path",
                "selection",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    obligatory_count = sum(1 for r in rows if r["selection"] == "obligatory")
    print()
    print(f"total: {len(rows)} ({obligatory_count} obligatory + random)")
    print(f"CSV: {OUT_CSV}")


if __name__ == "__main__":
    asyncio.run(_build_sample())
