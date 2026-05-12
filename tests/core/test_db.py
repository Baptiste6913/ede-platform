"""Tests for src.core.db plumbing.

Phase 0 only validates the factory/dispose plumbing and the error branch of
`ping()`. Real connectivity tests run in phase 1 with an actual DB fixture.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core import db
from src.core.exceptions import DatabaseError


@pytest.fixture(autouse=True)
def _reset_db_singletons() -> None:
    db._engine = None
    db._sessionmaker = None


def test_get_engine_is_cached() -> None:
    e1 = db.get_engine()
    e2 = db.get_engine()
    assert e1 is e2


def test_get_sessionmaker_binds_to_engine() -> None:
    sm = db.get_sessionmaker()
    assert sm is db.get_sessionmaker()
    assert sm.kw["bind"] is db.get_engine()


async def test_dispose_engine_clears_singletons() -> None:
    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    db._engine = fake_engine
    db._sessionmaker = MagicMock()

    await db.dispose_engine()

    fake_engine.dispose.assert_awaited_once()
    assert db._engine is None
    assert db._sessionmaker is None


async def test_dispose_engine_is_noop_when_uninitialized() -> None:
    db._engine = None
    db._sessionmaker = None
    await db.dispose_engine()
    assert db._engine is None


async def test_ping_returns_ok_on_success() -> None:
    fake_conn = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one.return_value = 1
    fake_conn.execute = AsyncMock(return_value=fake_result)

    fake_engine = MagicMock()
    fake_engine.connect.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
    fake_engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch.object(db, "get_engine", return_value=fake_engine):
        result = await db.ping()

    assert result["ok"] is True
    assert "latency_ms" in result


async def test_ping_returns_error_on_driver_failure() -> None:
    fake_engine = MagicMock()
    fake_engine.connect.side_effect = RuntimeError("connection refused")

    with patch.object(db, "get_engine", return_value=fake_engine):
        result = await db.ping()

    assert result["ok"] is False
    assert "connection refused" in result["error"]


async def test_ping_raises_database_error_on_bad_select() -> None:
    fake_conn = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one.return_value = 0  # unexpected
    fake_conn.execute = AsyncMock(return_value=fake_result)

    fake_engine = MagicMock()
    fake_engine.connect.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
    fake_engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch.object(db, "get_engine", return_value=fake_engine), pytest.raises(DatabaseError):
        await db.ping()


async def test_session_scope_commits_on_success() -> None:
    fake_session = AsyncMock()
    sm_factory = MagicMock()
    sm_factory.return_value.__aenter__ = AsyncMock(return_value=fake_session)
    sm_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch.object(db, "get_sessionmaker", return_value=sm_factory):
        async with db.session_scope() as session:
            assert session is fake_session

    fake_session.commit.assert_awaited_once()
    fake_session.rollback.assert_not_awaited()


async def test_session_scope_rolls_back_on_exception() -> None:
    fake_session = AsyncMock()
    sm_factory = MagicMock()
    sm_factory.return_value.__aenter__ = AsyncMock(return_value=fake_session)
    sm_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    class _BoomError(Exception):
        pass

    with patch.object(db, "get_sessionmaker", return_value=sm_factory):
        scope: Any = db.session_scope()
        with pytest.raises(_BoomError):
            async with scope:
                raise _BoomError

    fake_session.commit.assert_not_awaited()
    fake_session.rollback.assert_awaited_once()
