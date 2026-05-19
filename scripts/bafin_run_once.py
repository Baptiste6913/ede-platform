"""Phase 5 — Step 9 live backfill runner.

Triggers `BafinPoller.run_backfill()` against the real BaFin site
(plain httpx — no ScrapingBee per Step-0 finding) and prints a
structured JSON summary on stdout + mirrors it to
`artifacts/phase-05/bafin-backfill.json`.

Usage:

    DATABASE_URL=... DATA_DIR=... \\
        python scripts/bafin_run_once.py [days_back]

`days_back` defaults to 365 (12-month window). Use 1825 for a 5-year
historical sweep.

Exit codes:
  0  success
  2  unexpected error — see stdout JSON
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import traceback
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from src.core.logging import configure_logging
from src.core.settings import get_settings
from src.ingestion.bafin.poller import BafinPoller

_log = structlog.get_logger("bafin.run_once")


async def main(days_back: int) -> int:
    configure_logging(level="INFO")
    settings = get_settings()
    started = datetime.now(tz=UTC)
    since = date.today() - timedelta(days=days_back)

    poller = BafinPoller()
    try:
        result = await poller.run_backfill(since=since)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "phase": "bafin_run_once",
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": traceback.format_exc().splitlines()[-12:],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        with contextlib.suppress(Exception):
            await poller.aclose()
        return 2

    finished = datetime.now(tz=UTC)
    await poller.aclose()

    payload: dict[str, Any] = {
        "phase": "bafin_run_once",
        "status": "ok",
        "result": {
            "discovered": result.discovered,
            "created": result.created,
            "skipped": result.skipped,
            "pdf_downloaded": result.pdf_downloaded,
            "pdf_failed": result.pdf_failed,
            "stopped_on_known": result.stopped_on_known,
        },
        "timing": {
            "started_at_utc": started.isoformat(),
            "finished_at_utc": finished.isoformat(),
            "duration_seconds": round((finished - started).total_seconds(), 2),
        },
        "settings": {
            "data_dir": settings.data_dir,
            "since": since.isoformat(),
            "days_back": days_back,
            "rate_per_second": settings.poller_amf_rate_per_second,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    artifacts = Path("artifacts/phase-05")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "bafin-backfill.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _log.info(
        "bafin.run_once.done",
        discovered=result.discovered,
        created=result.created,
        pdf_downloaded=result.pdf_downloaded,
    )
    return 0


if __name__ == "__main__":
    days_back_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    sys.exit(asyncio.run(main(days_back_arg)))
