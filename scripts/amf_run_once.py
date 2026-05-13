"""One-shot AMF poller runner for manual / phase-2 live backfill.

Usage (inside a Python env with the project deps installed):

    DATABASE_URL=... DATA_DIR=... python scripts/amf_run_once.py

Prints the run summary as JSON on stdout, plus a short table of HTTP request
details captured via an httpx event hook.
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from typing import Any

import httpx
import structlog

from src.core.logging import configure_logging
from src.core.settings import get_settings
from src.ingestion.amf.poller import AmfPoller
from src.ingestion.amf.rate_limiter import RateLimiter

_log = structlog.get_logger("amf.run_once")


async def main() -> int:
    configure_logging(level="INFO")
    settings = get_settings()

    # Snapshot HTTP details so we can show the user the first request status
    # (anti-Akamai check).
    http_log: list[dict[str, Any]] = []

    async def _on_response(resp: httpx.Response) -> None:
        try:
            await resp.aread()
        except Exception:  # noqa: BLE001
            pass
        http_log.append(
            {
                "method": resp.request.method,
                "url": str(resp.request.url),
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
    poller = AmfPoller(client=client, rate_limiter=rl)
    try:
        result = await poller.run_once()
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "phase": "amf_run_once",
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "http_log": http_log,
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
        "phase": "amf_run_once",
        "status": "ok",
        "result": {
            "matched": result.matched,
            "created": result.created,
            "skipped": result.skipped,
            "pdf_downloaded": result.pdf_downloaded,
            "pdf_failed": result.pdf_failed,
        },
        "http_log": http_log,
        "settings": {
            "amf_rss_url": settings.amf_rss_url,
            "data_dir": settings.data_dir,
            "user_agent": settings.user_agent,
            "accept_language": settings.poller_amf_accept_language,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
