"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.settings import get_settings


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force ENV=test and a dummy DB url so settings never read real .env."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("EDE_API_TOKEN", "test-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def stub_db_ping_ok() -> Iterator[AsyncMock]:
    """Replace src.core.db.ping with a stub returning ok=True."""
    mock = AsyncMock(return_value={"ok": True, "latency_ms": 0.42})
    with patch("src.core.db.ping", mock):
        yield mock


@pytest.fixture
def stub_db_ping_fail() -> Iterator[AsyncMock]:
    """Replace src.core.db.ping with a stub returning ok=False."""
    mock = AsyncMock(return_value={"ok": False, "error": "connection refused"})
    with patch("src.core.db.ping", mock):
        yield mock


@pytest.fixture
async def async_client(stub_db_ping_ok: AsyncMock) -> AsyncIterator[AsyncClient]:
    """ASGI HTTP client against the FastAPI app, with DB ping stubbed."""
    _ = stub_db_ping_ok  # ensure fixture activates
    # Import inside the fixture so env vars set above are picked up.
    from src.api.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def pytest_configure(config: Any) -> None:
    """Disable real network at the asyncio level — defense in depth."""
    os.environ.setdefault("NO_PROXY", "*")
