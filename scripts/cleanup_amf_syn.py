"""Phase 4bis cleanup of legacy `AMF-SYN-*` deals + audit log.

Workflow:
    1. Connect to DATABASE_URL.
    2. SELECT all matching rows, write a structured audit log to
       `artifacts/phase-04bis/cleanup-log.txt` BEFORE deletion.
    3. Run `alembic upgrade head` which applies migration 0005 (the actual
       DELETE — also defensively counts before deleting).
    4. Verify post-state: `regulator_ref LIKE 'AMF-SYN-%'` count == 0.

Run separately *after* `scripts/backup_db.py` has produced a pg_dump in
the same artifacts directory.

Exit codes: 0 on success (including no-rows-to-delete), 1 on any failure.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.settings import get_settings


async def _capture_pre_delete(audit_log: Path) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, regulator_ref, target_name, acquirer_name, "
                        "       deal_type, announcement_date, created_at, source_url "
                        "FROM deals "
                        "WHERE regulator_ref LIKE 'AMF-SYN-%' "
                        "ORDER BY id"
                    )
                )
            ).all()
    finally:
        await engine.dispose()

    now = datetime.now(tz=UTC).isoformat()
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# AMF-SYN-* cleanup audit log\n"
        f"# Captured before DELETE: {now}\n"
        f"# Total matching rows:    {len(rows)}\n"
        f"# Database URL:           {settings.database_url}\n"
        "#\n"
    )
    payload: dict[str, Any] = {
        "captured_at_utc": now,
        "database_url": settings.database_url,
        "total_matching_rows": len(rows),
        "rows": [
            {
                "id": r.id,
                "regulator_ref": r.regulator_ref,
                "target_name": r.target_name,
                "acquirer_name": r.acquirer_name,
                "deal_type": r.deal_type,
                "announcement_date": r.announcement_date.isoformat()
                if r.announcement_date
                else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "source_url": r.source_url,
            }
            for r in rows
        ],
    }
    audit_log.write_text(
        header + json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return len(rows)


async def _verify_post_delete() -> tuple[int, int]:
    """Returns (remaining_amf_syn_deals, orphan_events)."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True)
    try:
        async with engine.connect() as conn:
            remaining = (
                await conn.execute(
                    text("SELECT count(*) FROM deals WHERE regulator_ref LIKE 'AMF-SYN-%'")
                )
            ).scalar_one()
            # Any event whose deal_id doesn't exist in deals would be an
            # orphan. FK CASCADE should ensure this is always 0.
            orphans = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM events e "
                        "LEFT JOIN deals d ON d.id = e.deal_id "
                        "WHERE d.id IS NULL"
                    )
                )
            ).scalar_one()
    finally:
        await engine.dispose()
    return remaining, orphans


def _run_alembic_upgrade() -> int:
    alembic = shutil.which("alembic")
    if alembic is None:
        print("ERROR: alembic not on PATH", file=sys.stderr)
        return 1
    result = subprocess.run(  # noqa: S603 — alembic_bin resolved via shutil.which
        [alembic, "upgrade", "head"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
    return result.returncode


async def main() -> int:
    audit_log = Path("artifacts/phase-04bis/cleanup-log.txt")

    pre_count = await _capture_pre_delete(audit_log)
    print(f"[1/3] captured {pre_count} AMF-SYN-* rows → {audit_log}")

    rc = _run_alembic_upgrade()
    if rc != 0:
        print(f"[2/3] alembic upgrade FAILED (exit {rc})", file=sys.stderr)
        return 1
    print("[2/3] alembic upgrade head → 0005 applied")

    remaining, orphans = await _verify_post_delete()
    print(f"[3/3] post-state: remaining AMF-SYN-*={remaining}, orphan events={orphans}")
    if remaining != 0 or orphans != 0:
        print("FAIL — non-zero post-state", file=sys.stderr)
        return 1

    deleted = pre_count - remaining
    print(f"OK deleted={deleted} pre_count={pre_count} remaining=0 orphan_events=0")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
