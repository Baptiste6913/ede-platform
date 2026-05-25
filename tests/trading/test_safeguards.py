"""Tests for safeguards — pure checks + KillSwitch (file) + SystemStateStore (DB)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from src.trading.safeguards import (
    KillSwitch,
    SystemStateStore,
    cooldown_active,
    daily_loss_breached,
    position_cap_reached,
)


# ----------------------------------------------------------- pure checks
def test_position_cap_reached():
    assert position_cap_reached(5, 5) is True
    assert position_cap_reached(6, 5) is True
    assert position_cap_reached(4, 5) is False


def test_daily_loss_breached():
    assert daily_loss_breached(980_000, 1_000_000, 0.02) is True  # -2.0%
    assert daily_loss_breached(981_000, 1_000_000, 0.02) is False  # -1.9%
    assert daily_loss_breached(1_010_000, 1_000_000, 0.02) is False  # up
    assert daily_loss_breached(900_000, 0.0, 0.02) is False  # no baseline


def test_cooldown_active():
    now = datetime(2026, 5, 21, 12, 0, tzinfo=UTC)
    assert cooldown_active(None, now, 60) is False
    assert cooldown_active(now - timedelta(minutes=30), now, 60) is True
    assert cooldown_active(now - timedelta(minutes=90), now, 60) is False


# ------------------------------------------------------------ kill switch
def test_kill_switch_file(tmp_path):
    ks = KillSwitch(tmp_path / "kill.flag")
    assert ks.is_active() is False
    ks.activate("manual stop")
    assert ks.is_active() is True
    ks.deactivate()
    assert ks.is_active() is False
    ks.deactivate()  # idempotent (missing_ok)


# --------------------------------------------------- system state (DB)
@pytest.mark.integration
async def test_system_state_set_get(db_session):
    store = SystemStateStore(db_session)
    assert await store.get("missing") is None
    await store.set("k", "v")
    assert await store.get("k") == "v"
    await store.set("k", "v2")  # upsert
    assert await store.get("k") == "v2"
    assert await store.get_int("n", 7) == 7
    await store.set("n", 3)
    assert await store.get_int("n") == 3


@pytest.mark.integration
async def test_rampup_increment(db_session):
    store = SystemStateStore(db_session)
    assert await store.rampup_validated() == 0
    assert await store.increment_rampup() == 1
    assert await store.increment_rampup() == 2
    assert await store.rampup_validated() == 2


@pytest.mark.integration
async def test_daily_baseline_resets_on_new_day(db_session):
    store = SystemStateStore(db_session)
    d1 = date(2026, 5, 21)
    assert await store.ensure_daily_baseline(1_000_000, d1) == 1_000_000
    # same day → keeps baseline even if NLV moved
    assert await store.ensure_daily_baseline(900_000, d1) == 1_000_000
    # new day → resets
    assert await store.ensure_daily_baseline(900_000, date(2026, 5, 22)) == 900_000


@pytest.mark.integration
async def test_last_order_ts_roundtrip(db_session):
    store = SystemStateStore(db_session)
    assert await store.last_order_ts() is None
    now = datetime(2026, 5, 21, 9, 0, tzinfo=UTC)
    await store.set_last_order_now(now)
    assert await store.last_order_ts() == now
