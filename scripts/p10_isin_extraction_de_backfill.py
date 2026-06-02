"""P10 Step 2a — back-fill the 4 DE labelled deals whose
``regulator_ref`` follows the legacy ``BAFIN-<name>-<date>`` format
(no ISIN in the ref) and therefore have ``ticker_target IS NULL``.

The fix mirrors Step 1 (FR): extract the first DE-prefixed 12-char
ISIN from the first 3 pages of the BaFin Angebotsunterlage PDF and
persist into ``deals.ticker_target``.

Mode
----
- default (no flag) = DRY-RUN
- ``--apply`` commits per-row UPDATE in a single transaction

Idempotent: scope filters on ``ticker_target IS NULL`` so re-runs
are a no-op for already-backfilled rows.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal
from src.core.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "data" / "audits" / "p10_isin_extraction_de_backfill.csv"

_ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b")
_DE_PREFIX = "DE"
_MAX_PAGES = 3


def _local_pdf(stored: str | None) -> Path | None:
    if not stored:
        return None
    rel = stored.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


def _extract_de_isin(pdf_path: Path) -> tuple[str | None, str]:
    try:
        pieces: list[str] = []
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                if i >= _MAX_PAGES:
                    break
                pieces.append(page.get_text("text") or "")
        text = "\n".join(pieces)
    except Exception as exc:
        return (None, f"pdf_error:{type(exc).__name__}")

    for m in _ISIN_RE.finditer(text):
        candidate = m.group(1)
        if candidate.startswith(_DE_PREFIX):
            return (candidate, "ok")
    return (None, "no_isin")


async def _process(*, dry_run: bool) -> None:
    engine = create_async_engine(get_settings().database_url, echo=False, future=True)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"[STEP-2a] mode: {mode}")

    rows: list[dict[str, str]] = []
    applied = 0
    skipped = 0

    async with sm() as session:
        deals = (
            (
                await session.execute(
                    select(Deal)
                    .where(
                        Deal.juridiction == "DE",
                        Deal.completion_label.isnot(None),
                        Deal.ticker_target.is_(None),
                    )
                    .order_by(Deal.id)
                )
            )
            .scalars()
            .all()
        )
        total = len(deals)
        print(f"[STEP-2a] {total} DE labelled deals to process")

        for deal in deals:
            pdf = _local_pdf(deal.pdf_path)
            if pdf is None:
                rows.append(
                    {
                        "deal_id": str(deal.id),
                        "regulator_ref": deal.regulator_ref,
                        "target_name": deal.target_name,
                        "isin": "",
                        "status": "skipped_no_pdf",
                    }
                )
                skipped += 1
                continue
            isin, status = _extract_de_isin(pdf)
            if isin is None:
                rows.append(
                    {
                        "deal_id": str(deal.id),
                        "regulator_ref": deal.regulator_ref,
                        "target_name": deal.target_name,
                        "isin": "",
                        "status": f"skipped_{status}",
                    }
                )
                skipped += 1
                continue
            if not dry_run:
                await session.execute(
                    update(Deal).where(Deal.id == deal.id).values(ticker_target=isin)
                )
            rows.append(
                {
                    "deal_id": str(deal.id),
                    "regulator_ref": deal.regulator_ref,
                    "target_name": deal.target_name,
                    "isin": isin,
                    "status": "applied",
                }
            )
            applied += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["deal_id", "regulator_ref", "target_name", "isin", "status"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"applied : {applied}")
    print(f"skipped : {skipped}")
    for r in rows:
        print(f"  {r['status']:<25} {r['regulator_ref'][:40]:<40} -> {r['isin']}")
    print()
    print(f"CSV     : {OUT_CSV}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="P10 Step 2a DE ISIN backfill")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    asyncio.run(_process(dry_run=not args.apply))
