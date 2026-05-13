"""Async rate limiter with positive jitter and exponential backoff.

`RateLimiter.acquire()` blocks until the next call slot is available, with a
small positive jitter to look less robotic. `retry_with_backoff` wraps an
async callable, retrying on `httpx.HTTPStatusError` 429/503 (and a few
related transient errors) using exponential backoff.

Per CLAUDE.md §4: "Rate limits : 1-2 req/s AMF, … exponential backoff,
jamais de scraping agressif."
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import Final, TypeVar

import httpx
import structlog

from src.core.exceptions import RateLimitError

T = TypeVar("T")

_log = structlog.get_logger(__name__)

# HTTP status codes that should trigger a backoff-and-retry loop rather than
# a hard fail.
HTTP_TOO_MANY_REQUESTS: Final[int] = 429
_RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({HTTP_TOO_MANY_REQUESTS, 500, 502, 503, 504})


class RateLimiter:
    """Single-process async rate limiter.

    Enforces a minimum interval between successive `acquire()` returns.
    Adds a small *positive* jitter (uniform in [0, jitter_seconds]) so calls
    don't land in lockstep — important when several pollers share the limiter.
    """

    def __init__(
        self,
        rate_per_second: float,
        *,
        jitter_seconds: float = 0.0,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be > 0")
        if jitter_seconds < 0:
            raise ValueError("jitter_seconds must be >= 0")
        self._interval: float = 1.0 / rate_per_second
        self._jitter: float = jitter_seconds
        self._lock: asyncio.Lock = asyncio.Lock()
        self._last_call_monotonic: float = 0.0

    async def acquire(self) -> None:
        """Block until it's OK to issue the next request."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call_monotonic
            wait = self._interval - elapsed
            if self._jitter > 0:
                wait += random.uniform(0.0, self._jitter)  # noqa: S311 — jitter, not crypto
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call_monotonic = time.monotonic()


async def retry_with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 30.0,
    service: str = "amf",
) -> T:
    """Run `fn` with exponential backoff on transient HTTP errors.

    Retries on:
    - httpx.HTTPStatusError with status in {429, 500, 502, 503, 504}
    - httpx.TransportError (connection reset, timeout, etc.)

    After `max_retries` attempts, the last error is re-raised wrapped in
    `RateLimitError` if it was a 429, otherwise re-raised as-is.
    """
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            last_exc = exc
            if status not in _RETRYABLE_STATUS:
                raise
            if attempt >= max_retries:
                if status == HTTP_TOO_MANY_REQUESTS:
                    raise RateLimitError(service, f"429 after {max_retries} retries") from exc
                raise
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise

        delay = min(max_delay_seconds, base_delay_seconds * (2**attempt))
        _log.warning(
            "retry_backoff",
            service=service,
            attempt=attempt + 1,
            delay=delay,
            error=type(last_exc).__name__,
        )
        await asyncio.sleep(delay)

    # Unreachable — the loop either returns or raises.
    raise RuntimeError("retry_with_backoff: control flow bug")  # pragma: no cover
