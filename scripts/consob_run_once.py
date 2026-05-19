"""Phase 4 — Step 9 live backfill runner.

Triggers `ConsobPoller.run_backfill()` against the real Consob site
(ScrapingBee for the listing pages + direct httpx for the PDFs) and
prints a structured JSON summary on stdout. Captures the per-step
ScrapingBee credit consumption so the operator can verify the budget
math (~12 credits for a full 12-month backfill).

Usage:

    DATABASE_URL=... DATA_DIR=... SCRAPINGBEE_API_KEY=... \\
        python scripts/consob_run_once.py [max_pages]

`max_pages` defaults to 12 (covers ~12 months at 50 items/page).

Exit codes:
  0  success — at least `min_discovered` items found, no budget issue
  1  budget exhausted before the run completed (alembic 0006 trigger)
  2  unexpected error (DB, ScrapingBee, etc.) — see stdout JSON
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from src.core.logging import configure_logging
from src.core.settings import get_settings
from src.ingestion.consob.poller import ConsobPoller

_log = structlog.get_logger("consob.run_once")


async def main(max_pages: int) -> int:
    configure_logging(level="INFO")
    settings = get_settings()
    started = datetime.now(tz=UTC)

    poller = ConsobPoller()
    credits_before = await poller._scrapingbee.used_credits_this_month()
    try:
        result = await poller.run_backfill(max_pages=max_pages)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "phase": "consob_run_once",
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
    credits_after = await poller._scrapingbee.used_credits_this_month()
    await poller.aclose()

    payload: dict[str, Any] = {
        "phase": "consob_run_once",
        "status": "ok" if not result.budget_exhausted else "budget_exhausted",
        "result": {
            "discovered": result.discovered,
            "created": result.created,
            "skipped": result.skipped,
            "pdf_downloaded": result.pdf_downloaded,
            "pdf_failed": result.pdf_failed,
            "credits_consumed_run": result.credits_consumed,
            "stopped_on_known": result.stopped_on_known,
            "budget_exhausted": result.budget_exhausted,
        },
        "scrapingbee": {
            "month_used_before": credits_before,
            "month_used_after": credits_after,
            "monthly_budget": settings.scrapingbee_monthly_budget,
            "remaining_this_month": settings.scrapingbee_monthly_budget - credits_after,
        },
        "timing": {
            "started_at_utc": started.isoformat(),
            "finished_at_utc": finished.isoformat(),
            "duration_seconds": round((finished - started).total_seconds(), 2),
        },
        "settings": {
            "data_dir": settings.data_dir,
            "scrapingbee_render_js": settings.scrapingbee_render_js,
            "scrapingbee_premium_proxy": settings.scrapingbee_premium_proxy,
            "rate_per_second": settings.poller_amf_rate_per_second,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    # Mirror to artifacts/phase-04/ for convenience.
    artifacts = Path("artifacts/phase-04")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "consob-backfill.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return 1 if result.budget_exhausted else 0


if __name__ == "__main__":
    max_pages_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    sys.exit(asyncio.run(main(max_pages_arg)))
