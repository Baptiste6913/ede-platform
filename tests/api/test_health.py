"""Tests for /health."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


async def test_health_returns_200_when_db_ok(async_client: AsyncClient) -> None:
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["uptime_seconds"] >= 0
    assert body["db"]["ok"] is True


async def test_health_degraded_when_db_down() -> None:
    from httpx import ASGITransport

    fail = AsyncMock(return_value={"ok": False, "error": "down"})
    with patch("src.core.db.ping", fail):
        from src.api.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"]["ok"] is False
    assert body["db"]["error"] == "down"


async def test_health_echoes_correlation_id(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/health",
        headers={"X-Correlation-Id": "abc-123"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-correlation-id") == "abc-123"


async def test_health_generates_correlation_id_when_absent(
    async_client: AsyncClient,
) -> None:
    resp = await async_client.get("/health")
    cid = resp.headers.get("x-correlation-id")
    assert cid is not None
    assert len(cid) >= 16  # uuid4 hex = 32 chars
