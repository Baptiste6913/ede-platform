"""Tests for src.ingestion.amf.rate_limiter."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.core.exceptions import RateLimitError
from src.ingestion.amf.rate_limiter import RateLimiter, retry_with_backoff


def test_rate_limiter_rejects_invalid_rate() -> None:
    with pytest.raises(ValueError, match="rate_per_second"):
        RateLimiter(0)
    with pytest.raises(ValueError, match="jitter_seconds"):
        RateLimiter(1.0, jitter_seconds=-0.1)


async def test_rate_limiter_first_acquire_no_wait() -> None:
    """First acquire should return immediately."""
    rl = RateLimiter(1.0)
    started = time.perf_counter()
    await rl.acquire()
    elapsed = time.perf_counter() - started
    assert elapsed < 0.05


async def test_rate_limiter_enforces_interval() -> None:
    """Two consecutive acquires must be separated by >= the interval.

    Patches asyncio.sleep so the test runs fast but still verifies the
    *requested* sleep duration.
    """
    rl = RateLimiter(2.0)  # 0.5s interval
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    with patch("src.ingestion.amf.rate_limiter.asyncio.sleep", side_effect=fake_sleep):
        await rl.acquire()  # first call, no sleep
        await rl.acquire()  # second call, ~0.5s sleep requested

    assert len(sleeps) == 1
    assert 0.45 <= sleeps[0] <= 0.55


async def test_rate_limiter_jitter_adds_positive_delay_only() -> None:
    rl = RateLimiter(2.0, jitter_seconds=0.2)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    with patch("src.ingestion.amf.rate_limiter.asyncio.sleep", side_effect=fake_sleep):
        await rl.acquire()
        await rl.acquire()

    # 0.5s interval + jitter ∈ [0, 0.2] => sleep ∈ [0.5, 0.7]
    assert len(sleeps) == 1
    assert 0.5 <= sleeps[0] <= 0.71


async def test_retry_backoff_returns_immediately_on_success() -> None:
    fn = AsyncMock(return_value="ok")
    result = await retry_with_backoff(fn, max_retries=3)
    assert result == "ok"
    assert fn.await_count == 1


async def test_retry_backoff_retries_on_429() -> None:
    """429 triggers retry, eventually raising RateLimitError."""
    response = httpx.Response(429, request=httpx.Request("GET", "https://example.test/x"))
    err = httpx.HTTPStatusError("rate limited", request=response.request, response=response)
    fn = AsyncMock(side_effect=err)

    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    with (
        patch("src.ingestion.amf.rate_limiter.asyncio.sleep", side_effect=fake_sleep),
        pytest.raises(RateLimitError),
    ):
        await retry_with_backoff(fn, max_retries=2, base_delay_seconds=1.0)

    # 3 attempts (initial + 2 retries) => 2 backoff sleeps with exp growth.
    assert fn.await_count == 3
    assert sleeps == pytest.approx([1.0, 2.0])


async def test_retry_backoff_retries_on_503_then_succeeds() -> None:
    """503 retries, then a successful response returns."""
    response = httpx.Response(503, request=httpx.Request("GET", "https://example.test/x"))
    err = httpx.HTTPStatusError("svc unavailable", request=response.request, response=response)
    fn = AsyncMock(side_effect=[err, err, "recovered"])

    with patch("src.ingestion.amf.rate_limiter.asyncio.sleep", new=AsyncMock()):
        result = await retry_with_backoff(fn, max_retries=5, base_delay_seconds=0.1)

    assert result == "recovered"
    assert fn.await_count == 3


async def test_retry_backoff_does_not_retry_on_404() -> None:
    """Non-retryable status (404) raises immediately."""
    response = httpx.Response(404, request=httpx.Request("GET", "https://example.test/x"))
    err = httpx.HTTPStatusError("not found", request=response.request, response=response)
    fn = AsyncMock(side_effect=err)

    with (
        patch("src.ingestion.amf.rate_limiter.asyncio.sleep", new=AsyncMock()),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await retry_with_backoff(fn, max_retries=3)

    assert fn.await_count == 1


async def test_retry_backoff_transport_error_retries() -> None:
    fn = AsyncMock(side_effect=[httpx.ConnectError("boom"), "ok"])
    with patch("src.ingestion.amf.rate_limiter.asyncio.sleep", new=AsyncMock()):
        result = await retry_with_backoff(fn, max_retries=2)
    assert result == "ok"
    assert fn.await_count == 2
