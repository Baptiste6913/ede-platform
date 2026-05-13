"""Take a pg_dump snapshot of the current Postgres DB.

Wraps `docker compose exec postgres pg_dump` so the operator can run a
backup with one command before any destructive migration. Output path:

    artifacts/<phase>/backup-pre-<reason>-<UTC-timestamp>.sql

Usage:

    python scripts/backup_db.py --phase phase-04bis --reason cleanup
    python scripts/backup_db.py --phase phase-04bis --reason cleanup --service postgres --db ede

Exit codes: 0 on success, 1 on pg_dump failure, 2 on filesystem errors.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, help="e.g. phase-04bis")
    parser.add_argument("--reason", required=True, help="e.g. cleanup")
    parser.add_argument("--service", default="postgres", help="docker compose service name")
    parser.add_argument("--db", default="ede", help="Postgres database name")
    parser.add_argument("--user", default="ede", help="Postgres user name")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "artifacts" / args.phase
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"backup-pre-{args.reason}-{ts}.sql"

    docker = shutil.which("docker")
    if docker is None:
        print("ERROR: docker not found on PATH", file=sys.stderr)
        return 2

    cmd = [
        docker,
        "compose",
        "exec",
        "-T",
        args.service,
        "pg_dump",
        "-U",
        args.user,
        "-d",
        args.db,
        "--format=plain",
        "--no-owner",
    ]
    try:
        with out_path.open("wb") as fh:
            result = subprocess.run(  # noqa: S603 — args constructed from CLI, docker from which
                cmd,
                stdout=fh,
                stderr=subprocess.PIPE,
                check=False,
                cwd=str(repo_root),
                timeout=600,
            )
    except subprocess.TimeoutExpired:
        print("ERROR: pg_dump timed out after 600s", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: filesystem failure: {exc}", file=sys.stderr)
        return 2

    if result.returncode != 0:
        print("ERROR: pg_dump failed", file=sys.stderr)
        print(result.stderr.decode("utf-8", errors="replace"), file=sys.stderr)
        out_path.unlink(missing_ok=True)
        return 1

    size = out_path.stat().st_size
    print(f"OK backup={out_path.relative_to(repo_root).as_posix()} bytes={size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
