"""P9.2 02b Step 1i — apply the Step 1h corrections to the DB.

Reads ``data/audits/p92_02b_re_run_comparison.csv``, filters rows whose
category is ``CORRECTED``, and applies ``UPDATE deals SET offer_price =
new_offer_price`` for each in a single transaction. Aborts (rolls back)
on the first error so the DB always lands in either the full pre-state
or the full post-state — never a partial one.

Pre-conditions enforced before any write:

- A backup must exist at ``artifacts/phase-09-02b/backup-pre-parser-fix-*.sql``
  (taken by ``scripts/backup_db.py --phase phase-09-02b --reason parser-fix``).
  The script bails out if no matching file is found.
- The comparison CSV must exist and contain at least one ``CORRECTED``
  row.
- Every targeted deal must still sit at
  ``offer_price_quality_flag = 'verified_cash'`` (defensive guard: if a
  parallel run promoted/demoted the row in the meantime, skip it).

Writes ``data/audits/p92_02b_db_update_log.csv`` with one row per
processed deal (applied / skipped / failed).

This script is a write operation. Re-running it after a successful pass
is idempotent at the row level (the new value matches the new value);
re-running it after a manual rollback re-applies the same updates.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal
from src.core.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPARISON_CSV = REPO_ROOT / "data" / "audits" / "p92_02b_re_run_comparison.csv"
LOG_CSV = REPO_ROOT / "data" / "audits" / "p92_02b_db_update_log.csv"
BACKUP_GLOB = REPO_ROOT / "artifacts" / "phase-09-02b"


def _to_decimal(s: str) -> Decimal | None:
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _load_corrections() -> list[dict[str, str]]:
    with COMPARISON_CSV.open(encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r["category"] == "CORRECTED"]


def _find_backup() -> Path | None:
    if not BACKUP_GLOB.is_dir():
        return None
    matches = sorted(BACKUP_GLOB.glob("backup-pre-parser-fix-*.sql"))
    return matches[-1] if matches else None


async def _apply(*, dry_run: bool) -> None:  # noqa: PLR0915 — single linear flow
    backup = _find_backup()
    if backup is None:
        print(
            "ERROR: no backup found at "
            f"{BACKUP_GLOB}/backup-pre-parser-fix-*.sql. "
            "Run `python scripts/backup_db.py --phase phase-09-02b "
            "--reason parser-fix` first.",
            file=sys.stderr,
        )
        sys.exit(2)
    print(f"[STEP-1i] backup: {backup.name} ({backup.stat().st_size:,} bytes)")

    corrections = _load_corrections()
    if not corrections:
        print("ERROR: no CORRECTED rows in the comparison CSV — nothing to do.")
        sys.exit(1)
    print(f"[STEP-1i] {len(corrections)} CORRECTED rows to apply")
    print(f"[STEP-1i] mode: {'DRY-RUN (no commit)' if dry_run else 'APPLY (transactional)'}")

    engine = create_async_engine(get_settings().database_url, echo=False, future=True)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    log_rows: list[dict[str, object]] = []
    applied = 0
    skipped_flag_drift = 0
    failed = 0

    async with sm() as session:
        # All UPDATEs in a single transaction. SQLAlchemy AsyncSession opens
        # one implicitly on first I/O; the commit at the end seals it. On any
        # exception we rollback and rethrow so the run aborts cleanly.
        try:
            for c in corrections:
                deal_id = int(c["deal_id"])
                new_price = _to_decimal(c["new_offer_price"])
                old_price_csv = _to_decimal(c["old_offer_price"])
                if new_price is None:
                    log_rows.append(_log_row(c, "skipped_invalid_new_price"))
                    failed += 1
                    continue

                deal = (
                    await session.execute(select(Deal).where(Deal.id == deal_id))
                ).scalar_one_or_none()
                if deal is None:
                    log_rows.append(_log_row(c, "skipped_missing_deal"))
                    failed += 1
                    continue

                # Defensive guard: the row must still be verified_cash AND the
                # current value must match the CSV's old_offer_price. Otherwise
                # a parallel write touched the row since Step 1h — skip rather
                # than overwrite.
                if deal.offer_price_quality_flag != "verified_cash":
                    log_rows.append(_log_row(c, "skipped_flag_drift"))
                    skipped_flag_drift += 1
                    continue
                if deal.offer_price != old_price_csv:
                    log_rows.append(_log_row(c, "skipped_price_drift"))
                    skipped_flag_drift += 1
                    continue

                await session.execute(
                    update(Deal).where(Deal.id == deal_id).values(offer_price=new_price)
                )
                log_rows.append(_log_row(c, "applied"))
                applied += 1

            if dry_run:
                await session.rollback()
                print("[STEP-1i] DRY-RUN — rolled back, no DB write")
            else:
                await session.commit()
                print(f"[STEP-1i] COMMITTED — {applied} rows updated")
        except Exception as exc:
            await session.rollback()
            print(f"ERROR: rolled back, {type(exc).__name__}: {exc}", file=sys.stderr)
            failed += 1
            raise

    await engine.dispose()
    _write_log(log_rows)

    print()
    print(f"applied            : {applied}")
    print(f"skipped (drift)    : {skipped_flag_drift}")
    print(f"failed             : {failed}")
    print(f"log CSV            : {LOG_CSV}")


def _log_row(c: dict[str, str], status: str) -> dict[str, object]:
    return {
        "deal_id": c["deal_id"],
        "regulator_ref": c["regulator_ref"],
        "target_name": c["target_name"],
        "old_offer_price": c["old_offer_price"],
        "new_offer_price": c["new_offer_price"],
        "new_source": c["new_source"],
        "update_timestamp": datetime.now(tz=UTC).isoformat(),
        "sql_status": status,
    }


def _write_log(rows: list[dict[str, object]]) -> None:
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    with LOG_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "deal_id",
                "regulator_ref",
                "target_name",
                "old_offer_price",
                "new_offer_price",
                "new_source",
                "update_timestamp",
                "sql_status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply P9.2 02b parser corrections to DB")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Commit the UPDATEs. Without this flag the script runs as a DRY-RUN.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_apply(dry_run=not args.apply))
