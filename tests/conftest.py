"""Shared pytest fixtures."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.settings import get_settings

_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ede:ede@localhost:5432/ede_test",
)


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
    mock = AsyncMock(return_value={"ok": True, "latency_ms": 0.42})
    with patch("src.core.db.ping", mock):
        yield mock


@pytest.fixture
def stub_db_ping_fail() -> Iterator[AsyncMock]:
    mock = AsyncMock(return_value={"ok": False, "error": "connection refused"})
    with patch("src.core.db.ping", mock):
        yield mock


@pytest.fixture
async def async_client(stub_db_ping_ok: AsyncMock) -> AsyncIterator[AsyncClient]:
    _ = stub_db_ping_ok
    from src.api.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def pytest_configure(config: Any) -> None:
    os.environ.setdefault("NO_PROXY", "*")
    config.addinivalue_line(
        "markers",
        "integration: tests that require a running PostgreSQL + TimescaleDB.",
    )


# =========================================================================
# Database fixtures (integration — require a live pg + timescaledb)
# =========================================================================


@pytest.fixture(scope="session")
def integration_db_url() -> str:
    return _TEST_DB_URL


@pytest.fixture(scope="session")
def _migrate_once(integration_db_url: str) -> Iterator[None]:
    """Run alembic downgrade base + upgrade head exactly once per session.

    Uses subprocess (sync) to avoid nesting asyncio.run inside the test's loop.
    Skips politely if the DB is not reachable.
    """
    alembic_bin = shutil.which("alembic")
    if alembic_bin is None:
        pytest.skip("alembic CLI not installed")

    # Probe connectivity (sync via psycopg URL doesn't exist; use a tiny socket attempt).
    env = {**os.environ, "DATABASE_URL": integration_db_url}
    # alembic_bin is resolved via shutil.which from PATH — not user input. The
    # subprocess args are static literals. S603 is a false positive here.
    # Reset to base (ignore failures: first run on empty DB has nothing to drop).
    subprocess.run(  # noqa: S603
        [alembic_bin, "downgrade", "base"],
        env=env,
        check=False,
        timeout=60,
    )
    result = subprocess.run(  # noqa: S603
        [alembic_bin, "upgrade", "head"],
        env=env,
        check=False,
        timeout=120,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"alembic upgrade failed; DB likely unreachable: {result.stderr}")
    yield


@pytest.fixture
async def db_engine(_migrate_once: None, integration_db_url: str) -> AsyncIterator[Any]:
    """Function-scoped engine. Migrations are session-scoped; engine itself is
    re-created per test so it lives in the test's own event loop.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(integration_db_url, future=True)
    yield engine
    await engine.dispose()


async def _truncate_all(db_engine: Any) -> None:
    """TRUNCATE every domain table. Shared by db_session teardown and the
    autouse cleanup for integration tests that build their own sessions."""
    from sqlalchemy import text as sa_text

    async with db_engine.begin() as conn:
        await conn.execute(
            sa_text(
                "TRUNCATE TABLE trades, paper_positions, analyses, scores, events, deals, "
                "prices, vendor_api_usage RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
async def db_clean(db_engine: Any) -> AsyncIterator[None]:
    """Yield, then truncate. Pull this fixture into any integration test that
    doesn't already depend on `db_session` (which truncates by itself)."""
    yield
    await _truncate_all(db_engine)


@pytest.fixture
async def db_session(db_engine: Any) -> AsyncIterator[Any]:
    """Function-scoped session. Truncates all tables after each test."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session

    await _truncate_all(db_engine)
