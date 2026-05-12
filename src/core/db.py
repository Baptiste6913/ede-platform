"""Async SQLAlchemy engine and session factory.

Phase 0 only exposes the plumbing. Schema/models land in phase 1.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.exceptions import DatabaseError
from src.core.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models (phase 1+ populates this)."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        future=True,
    )


def get_engine() -> AsyncEngine:
    """Return the lazily-initialized async engine."""
    global _engine  # noqa: PLW0603 — module-level singleton
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker  # noqa: PLW0603 — module-level singleton
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context manager yielding an AsyncSession with commit/rollback."""
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping() -> dict[str, Any]:
    """Lightweight connectivity probe used by /health.

    Returns a dict with `ok: bool` and either `latency_ms` or `error`.
    """
    from time import perf_counter

    from sqlalchemy import text

    engine = get_engine()
    started = perf_counter()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar_one()
            if value != 1:
                raise DatabaseError("SELECT 1 returned unexpected value")
    except DatabaseError:
        raise
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "latency_ms": round((perf_counter() - started) * 1000, 2)}


async def dispose_engine() -> None:
    """Dispose the engine. Called on FastAPI shutdown."""
    global _engine, _sessionmaker  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
