"""One-shot BDIF poller runner for phase-3 live backfill.

Usage (inside a Python env with the project deps installed):

    DATABASE_URL=... DATA_DIR=... python scripts/bdif_run_once.py [max_items]

Defaults to 60 items (≈12 months of M&A notes at AMF's current cadence).
Prints the run summary as JSON on stdout, plus an HTTP audit log.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import traceback
from typing import Any

import httpx
import structlog

from src.core.logging import configure_logging
from src.core.settings import get_settings
from src.ingestion.amf.bdif_poller import BdifPoller
from src.ingestion.amf.rate_limiter import RateLimiter

_log = structlog.get_logger("amf.bdif.run_once")


async def main(max_items: int) -> int:
    configure_logging(level="INFO")
    settings = get_settings()

    http_log: list[dict[str, Any]] = []

    async def _on_response(resp: httpx.Response) -> None:
        with contextlib.suppress(httpx.HTTPError, RuntimeError):
            await resp.aread()
        http_log.append(
            {
                "method": resp.request.method,
                "url": str(resp.request.url)[:200],
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "content_length": int(resp.headers.get("content-length") or 0),
            }
        )

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.poller_amf_timeout_seconds),
        headers={
            "User-Agent": settings.user_agent,
            "Accept-Language": settings.poller_amf_accept_language,
        },
        follow_redirects=True,
        event_hooks={"response": [_on_response]},
    )
    rl = RateLimiter(
        settings.poller_amf_rate_per_second,
        jitter_seconds=settings.poller_amf_jitter_seconds,
    )
    poller = BdifPoller(client=client, rate_limiter=rl, max_items=max_items)
    try:
        result = await poller.run_once()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "phase": "bdif_run_once",
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "http_log_tail": http_log[-10:],
                    "traceback": traceback.format_exc().splitlines()[-12:],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1
    finally:
        await poller.aclose()

    payload = {
        "phase": "bdif_run_once",
        "status": "ok",
        "result": {
            "discovered": result.discovered,
            "created": result.created,
            "skipped": result.skipped,
            "pdf_downloaded": result.pdf_downloaded,
            "pdf_failed": result.pdf_failed,
        },
        "http_log_summary": {
            "total_requests": len(http_log),
            "by_status": _count_by_status(http_log),
            "first_request": http_log[0] if http_log else None,
            "last_request": http_log[-1] if http_log else None,
        },
        "settings": {
            "data_dir": settings.data_dir,
            "user_agent": settings.user_agent,
            "accept_language": settings.poller_amf_accept_language,
            "rate_per_second": settings.poller_amf_rate_per_second,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _count_by_status(log: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for entry in log:
        key = str(entry["status_code"])
        out[key] = out.get(key, 0) + 1
    return out


if __name__ == "__main__":
    max_items_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    sys.exit(asyncio.run(main(max_items_arg)))
