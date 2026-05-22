"""Tests for the scheduler — DST time maths (pure) + daily cycle (mocked deps)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.trading.decision_engine import DealCandidate, TradeRequest
from src.trading.ibkr_client import PriceSnapshot
from src.trading.safeguards import KillSwitch
from src.trading.scheduler import TradingScheduler, next_paris_time


# --------------------------------------------------- DST-aware scheduling
def test_next_paris_time_summer_is_utc_07():
    # 2026-07-01, before 09:00 Paris (CEST = UTC+2) ⇒ 09:00 Paris = 07:00 UTC.
    now = datetime(2026, 7, 1, 5, 0, tzinfo=UTC)
    assert next_paris_time(now, 9) == datetime(2026, 7, 1, 7, 0, tzinfo=UTC)


def test_next_paris_time_winter_is_utc_08():
    # 2026-01-15, CET = UTC+1 ⇒ 09:00 Paris = 08:00 UTC.
    now = datetime(2026, 1, 15, 5, 0, tzinfo=UTC)
    assert next_paris_time(now, 9) == datetime(2026, 1, 15, 8, 0, tzinfo=UTC)


def test_next_paris_time_rolls_to_next_day_when_past():
    # Already 08:00 UTC = 10:00 Paris (summer) ⇒ next 09:00 Paris is tomorrow 07:00 UTC.
    now = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    assert next_paris_time(now, 9) == datetime(2026, 7, 2, 7, 0, tzinfo=UTC)


def test_next_paris_time_dst_spring_forward():
    # DST starts 2026-03-29: before that day CET (UTC+1), on/after CEST (UTC+2).
    before = datetime(2026, 3, 27, 5, 0, tzinfo=UTC)
    assert next_paris_time(before, 9) == datetime(2026, 3, 27, 8, 0, tzinfo=UTC)  # CET
    after = datetime(2026, 3, 30, 5, 0, tzinfo=UTC)
    assert next_paris_time(after, 9) == datetime(2026, 3, 30, 7, 0, tzinfo=UTC)  # CEST


def test_next_paris_time_dst_fall_back():
    # DST ends 2026-10-25: before CEST (UTC+2), after CET (UTC+1).
    before = datetime(2026, 10, 23, 5, 0, tzinfo=UTC)
    assert next_paris_time(before, 9) == datetime(2026, 10, 23, 7, 0, tzinfo=UTC)  # CEST
    after = datetime(2026, 10, 27, 5, 0, tzinfo=UTC)
    assert next_paris_time(after, 9) == datetime(2026, 10, 27, 8, 0, tzinfo=UTC)  # CET


# ----------------------------------------------------------- mocked deps
class MockIbkr:
    async def qualify_contract(self, *a, **k):
        return object()

    async def qualify_by_isin(self, *a, **k):
        return object()

    async def get_current_price(self, contract):
        return PriceSnapshot(bid=10.0, ask=10.1, last=10.05, close=9.9, market_data_type=3)


class MockEngine:
    def __init__(self, req):
        self._req = req

    def evaluate(self, cand, snapshot, net_liq, open_positions, rampup):
        return self._req


class MockExecutor:
    def __init__(self, status):
        self._status = status
        self.calls = 0

    async def submit(self, session, req, **k):
        self.calls += 1
        from types import SimpleNamespace

        return SimpleNamespace(status=self._status)


class MockDiscord:
    def __init__(self):
        self.events = []

    async def kill_switch_active(self):
        self.events.append("kill")

    async def daily_loss_limit(self, pct):
        self.events.append("loss")

    async def trade_submitted(self, *a):
        self.events.append("submitted")

    async def trade_generated(self, *a):
        self.events.append("generated")


def _candidate():
    return DealCandidate(
        deal_id=1,
        target_name="Commerzbank",
        acquirer_name="UniCredit",
        juridiction="DE",
        offer_price=180.0,
        p_completion=0.95,
        score_stars=5,
        symbol="CBK",
        exchange="IBIS",
        isin=None,
    )


def _req(requires_approval=False):
    return TradeRequest(
        trade_id="t1",
        deal_id=1,
        deal_target="Commerzbank",
        deal_acquirer="UniCredit",
        side="BUY",
        quantity=100,
        symbol="CBK",
        exchange="IBIS",
        isin=None,
        currency="EUR",
        limit_price=10.0,
        stop_loss_price=9.0,
        take_profit_price=11.0,
        expected_p_completion=0.95,
        expected_return_pct=0.05,
        kelly_fractional_pct=0.1,
        position_pct=0.1,
        rationale="r",
        requires_approval=requires_approval,
    )


def _scheduler(req, status, kill_path, discord, settings):
    return TradingScheduler(
        ibkr=MockIbkr(),
        executor=MockExecutor(status),
        engine=MockEngine(req),
        discord=discord,
        kill_switch=KillSwitch(kill_path),
        settings=settings,
    )


async def test_kill_switch_halts_cycle(tmp_path):
    from src.core.settings import get_settings

    kill = tmp_path / "kill.flag"
    ks = KillSwitch(kill)
    ks.activate("test")
    discord = MockDiscord()
    sched = _scheduler(_req(), "SUBMITTED", kill, discord, get_settings())
    summary = await sched.run_daily_cycle(None, [_candidate()], 1_000_000)
    assert summary.halted == "kill_switch"
    assert discord.events == ["kill"]


@pytest.mark.integration
async def test_daily_loss_halts_and_arms_kill_switch(db_session, tmp_path):
    from src.core.settings import get_settings

    discord = MockDiscord()
    sched = _scheduler(_req(), "SUBMITTED", tmp_path / "k.flag", discord, get_settings())
    # baseline 1M, then NLV 970k = -3% > 2% limit.
    from src.trading.safeguards import SystemStateStore

    await SystemStateStore(db_session).ensure_daily_baseline(1_000_000)
    summary = await sched.run_daily_cycle(db_session, [_candidate()], 970_000)
    assert summary.halted == "daily_loss"
    assert "loss" in discord.events
    assert sched.kill_switch.is_active()


@pytest.mark.integration
async def test_happy_cycle_submits(db_session, tmp_path):
    from src.core.settings import get_settings

    discord = MockDiscord()
    sched = _scheduler(
        _req(requires_approval=False), "SUBMITTED", tmp_path / "k.flag", discord, get_settings()
    )
    summary = await sched.run_daily_cycle(db_session, [_candidate()], 1_000_000)
    assert summary.submitted == ["t1"]
    assert "submitted" in discord.events


@pytest.mark.integration
async def test_rampup_cycle_pends_for_approval(db_session, tmp_path):
    from src.core.settings import get_settings

    discord = MockDiscord()
    sched = _scheduler(
        _req(requires_approval=True), "PENDING", tmp_path / "k.flag", discord, get_settings()
    )
    summary = await sched.run_daily_cycle(db_session, [_candidate()], 1_000_000)
    assert summary.pending_approval == ["t1"]
    assert "generated" in discord.events


class _NoQualifyIbkr:
    async def qualify_contract(self, *a, **k):
        return None

    async def qualify_by_isin(self, *a, **k):
        return None

    async def get_current_price(self, contract):
        raise AssertionError("should not price an unqualified contract")


@pytest.mark.integration
async def test_baseline_persists_when_zero_trades_submitted(db_session, db_engine, tmp_path):
    """Daily baseline must be committed even when no trade is submitted, so the
    daily-loss safeguard survives across cycles (Step-11 dry-run bug)."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.core.settings import get_settings
    from src.trading.safeguards import KEY_DAILY_BASELINE, SystemStateStore

    discord = MockDiscord()
    sched = TradingScheduler(
        ibkr=_NoQualifyIbkr(),
        executor=MockExecutor("SUBMITTED"),
        engine=MockEngine(_req()),
        discord=discord,
        kill_switch=KillSwitch(tmp_path / "k.flag"),
        settings=get_settings(),
    )
    summary = await sched.run_daily_cycle(db_session, [_candidate()], 1_000_000)
    assert summary.submitted == [] and summary.pending_approval == []  # nothing traded

    # A FRESH session must see the committed baseline.
    async with AsyncSession(db_engine, expire_on_commit=False) as fresh:
        val = await SystemStateStore(fresh).get(KEY_DAILY_BASELINE)
    assert val is not None
    assert float(val) == 1_000_000.0
