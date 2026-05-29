"""P9.2 02a commit #3 — backfill 730 FR historical deals through the post-fix
AMF parser.

Targets every juridiction='FR' deal whose offer_price_quality_flag is still
the migration-0015 default (`suspect_low_unverified`). For each, re-runs
`amf_parser.extract_pdf_metadata` on the stored PDF and applies the same
back-fill rule the live service uses (Option A):

- If the parser returns a non-null offer_price, update offer_price /
  currency / offer_price_quality_flag (via service._derive_quality_flag) /
  parser_version = 2.
- If the parser returns None, keep the row at suspect_low_unverified but
  still stamp parser_version = 2 so a subsequent run skips it (idempotence).
- Rows already promoted to a non-default flag are left untouched (the live
  service idempotence guard).

Score invalidation: at the end (apply mode), every FR deal whose
parser_version was bumped to 2 has its rows in `scores` deleted, so the
Phase-6 scorer can recompute on the corrected prices. Per the 02d lesson
the actual prediction probably does not move (the scorer is largely
flag-agnostic), but the invalidation is kept as an architectural
discipline — the offer_price changed under the score's feet.

Modes:
- default (no flag)    : dry-run. Computes everything, writes the CSV,
                         prints the summary, BUT performs zero DB writes
                         (parser_version stays at 1, scores stay intact).
- --apply              : commits per deal + runs the score invalidation
                         at the end.

CSV: data/audits/p92_02a_backfill_results.csv

Run (PowerShell, repo root, postgres up):
  $env:DATABASE_URL = "postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/backfill_p92_02a.py            # dry-run
  .venv/Scripts/python.exe scripts/backfill_p92_02a.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import sys
from decimal import Decimal
from pathlib import Path

# Standalone invocation: make `src` importable before the first-party imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.models import Deal, Score
from src.core.settings import get_settings
from src.ingestion.amf.parser import extract_pdf_metadata
from src.ingestion.amf.service import PARSER_VERSION_02A, _derive_quality_flag

_log = structlog.get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "data" / "audits" / "p92_02a_backfill_results.csv"

DEFAULT_FLAG = "suspect_low_unverified"

FIELDNAMES = [
    "deal_id",
    "regulator_ref",
    "target_company",
    "pdf_path",
    "old_price",
    "new_price",
    "old_flag",
    "new_flag",
    "action",
]


def _local_pdf(pdf_path: str | None) -> Path | None:
    """Map a stored pdf_path to the local working tree, or None if unusable."""
    if not pdf_path:
        return None
    rel = pdf_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


async def _invalidate_scores(session: AsyncSession) -> int:
    """Delete `scores` rows for every FR deal whose parser_version was bumped
    to PARSER_VERSION_02A in this run. Returns the deleted count.

    Per the 02d lesson the scorer is largely flag-agnostic, so prediction
    values probably do not move. The invalidation is kept as discipline: the
    offer_price changed under the score's feet, so the score is stale by
    definition until Phase 6 re-runs.
    """
    target = select(Deal.id).where(
        Deal.juridiction == "FR",
        Deal.parser_version == PARSER_VERSION_02A,
    )
    count = (
        await session.execute(
            select(func.count()).select_from(Score).where(Score.deal_id.in_(target))
        )
    ).scalar_one()
    await session.execute(delete(Score).where(Score.deal_id.in_(target)))
    await session.commit()
    return int(count)


def _row(
    *,
    deal_id: int,
    regulator_ref: str,
    target_company: str,
    pdf_path: str,
    old_price: Decimal | None,
    new_price: Decimal | None,
    old_flag: str,
    new_flag: str,
    action: str,
) -> dict[str, object]:
    return {
        "deal_id": deal_id,
        "regulator_ref": regulator_ref,
        "target_company": target_company,
        "pdf_path": pdf_path,
        "old_price": str(old_price) if old_price is not None else "",
        "new_price": str(new_price) if new_price is not None else "",
        "old_flag": old_flag,
        "new_flag": new_flag,
        "action": action,
    }


async def _backfill(*, apply: bool) -> None:
    rows: list[dict[str, object]] = []
    # Dedicated engine without `pool_pre_ping`: the global engine's pre-ping
    # path triggers a sync-via-greenlet ping that misfires in this standalone
    # script context. Async sessions still work, just without the per-checkout
    # ping (script lifetime is short, the pool stays warm).
    engine = create_async_engine(get_settings().database_url, echo=False, future=True)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    mode_label = "APPLY" if apply else "DRY-RUN"
    print(f"[{mode_label}] starting AMF P9.2 02a backfill...")

    async with sm() as session:
        # Scope: every FR deal still at the default flag whose parser_version
        # is strictly below the current revision. The parser_version guard is
        # what gives the script true idempotence: a re-run after a successful
        # apply matches zero rows (every applied deal — including silent_miss
        # rows that stay at suspect_low_unverified by design — was stamped to
        # PARSER_VERSION_02A and is therefore excluded). Mirrors the P9.1a
        # backfill pattern.
        stmt = (
            select(Deal)
            .where(
                Deal.juridiction == "FR",
                Deal.offer_price_quality_flag == DEFAULT_FLAG,
                Deal.parser_version < PARSER_VERSION_02A,
            )
            .order_by(Deal.id)
        )
        deals = (await session.execute(stmt)).scalars().all()
        total = len(deals)
        print(f"[{mode_label}] {total} FR deals at default flag — re-parsing...")

        for idx, deal in enumerate(deals, start=1):
            # Snapshot all attrs upfront: a per-deal rollback (dry-run path)
            # expires the ORM state and a later `deal.id` access forces a
            # sync-style lazy reload that misfires in this async context.
            deal_id = deal.id
            regulator_ref = deal.regulator_ref
            target_company = deal.target_name
            pdf_path = deal.pdf_path or ""
            old_price = deal.offer_price
            old_flag = deal.offer_price_quality_flag
            local = _local_pdf(deal.pdf_path)

            if local is None:
                rows.append(
                    _row(
                        deal_id=deal_id,
                        regulator_ref=regulator_ref,
                        target_company=target_company,
                        pdf_path=pdf_path,
                        old_price=old_price,
                        new_price=old_price,
                        old_flag=old_flag,
                        new_flag=old_flag,
                        action="skipped_no_pdf",
                    )
                )
                if idx % 50 == 0:
                    print(f"[{mode_label}] progress: {idx}/{total} (last action=skipped_no_pdf)")
                continue

            try:
                md = extract_pdf_metadata(local)
            except Exception as exc:
                _log.warning(
                    "p92_02a.backfill.parser_exception",
                    deal_id=deal_id,
                    ref=regulator_ref,
                    pdf=str(local),
                    error=str(exc),
                )
                rows.append(
                    _row(
                        deal_id=deal_id,
                        regulator_ref=regulator_ref,
                        target_company=target_company,
                        pdf_path=pdf_path,
                        old_price=old_price,
                        new_price=old_price,
                        old_flag=old_flag,
                        new_flag=old_flag,
                        action="exception",
                    )
                )
                if idx % 50 == 0:
                    print(f"[{mode_label}] progress: {idx}/{total} (last action=exception)")
                continue

            new_flag = _derive_quality_flag(md)
            new_price = md.offer_price

            # Idempotent rule: only mutate when the row is still at the default
            # flag (which it must be, per the WHERE clause above — defensive in
            # case the live service writes between SELECT and UPDATE).
            if old_flag == DEFAULT_FLAG:
                if apply:
                    deal.offer_price = new_price
                    deal.currency = md.currency or deal.currency or "EUR"
                    deal.offer_price_quality_flag = new_flag
                    deal.parser_version = PARSER_VERSION_02A
                    await session.commit()  # transactional per deal
                # Dry-run: do NOT mutate the ORM (a later rollback would
                # expire `deal.*` access and re-trigger the MissingGreenlet).
                action = "applied"
            else:
                action = "noop"

            rows.append(
                _row(
                    deal_id=deal_id,
                    regulator_ref=regulator_ref,
                    target_company=target_company,
                    pdf_path=pdf_path,
                    old_price=old_price,
                    new_price=new_price,
                    old_flag=old_flag,
                    new_flag=new_flag,
                    action=action,
                )
            )
            if idx % 50 == 0:
                print(f"[{mode_label}] progress: {idx}/{total} (last action={action})")

        scores_deleted = await _invalidate_scores(session) if apply else 0

    await engine.dispose()
    _write_csv(rows)
    _print_summary(rows, scores_deleted=scores_deleted, apply=apply)


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(rows: list[dict[str, object]], *, scores_deleted: int, apply: bool) -> None:
    by_action: dict[str, int] = {}
    by_new_flag: dict[str, int] = {}
    applied_prices: list[Decimal] = []
    for r in rows:
        by_action[str(r["action"])] = by_action.get(str(r["action"]), 0) + 1
        by_new_flag[str(r["new_flag"])] = by_new_flag.get(str(r["new_flag"]), 0) + 1
        if r["action"] == "applied" and r["new_price"]:
            applied_prices.append(Decimal(str(r["new_price"])))

    mode_label = "APPLY" if apply else "DRY-RUN"
    print()
    print("=" * 72)
    print(f"P9.2 02a backfill {mode_label} — AMF FR offer_price re-parse")
    print("=" * 72)
    print(f"deals processed: {len(rows)}")
    print()
    print("by action:")
    for action in sorted(by_action):
        print(f"  {action:<20}: {by_action[action]}")
    print()
    print("by new_flag:")
    for flag in sorted(by_new_flag):
        print(f"  {flag:<24}: {by_new_flag[flag]}")
    print()
    if applied_prices:
        sp = sorted(applied_prices)
        n = len(sp)
        p05 = sp[max(0, int(n * 0.05) - 1)]
        p95 = sp[min(n - 1, int(n * 0.95))]
        print("applied price distribution (EUR):")
        print(f"  count : {n}")
        print(f"  min   : {sp[0]}")
        print(f"  p05   : {p05}")
        print(f"  median: {statistics.median(applied_prices)}")
        print(f"  p95   : {p95}")
        print(f"  max   : {sp[-1]}")
        print()
    if apply:
        print(f"scores deleted (FR + parser_version=2): {scores_deleted}")
    else:
        print("scores deleted: 0 (dry-run — no DB writes)")
    print()
    print(f"CSV: {OUTPUT}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="P9.2 02a AMF FR backfill")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Commit DB mutations + invalidate scores. Without this flag the script is a dry-run.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_backfill(apply=args.apply))
