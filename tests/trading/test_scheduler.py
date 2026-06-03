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


class MockPriceProvider:
    """Decision-time price source returning a fixed snapshot (no broker)."""

    async def get_snapshot(self, candidate):
        return PriceSnapshot(bid=10.0, ask=10.1, last=10.05, close=9.9, market_data_type=3)


class MockNoPriceProvider:
    """Price source that finds no price ⇒ candidate skipped, zero decisions."""

    async def get_snapshot(self, candidate):
        return None


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
        price_provider=MockPriceProvider(),
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


async def test_snapshot_uses_price_provider_not_ibkr():
    """Decision-time pricing comes from the injected provider, never IBKR —
    proves the calculation runs with no broker (ibkr=None, executor=None)."""
    from src.core.settings import get_settings

    sched = TradingScheduler(
        ibkr=None,
        executor=None,
        engine=MockEngine(_req()),
        discord=MockDiscord(),
        settings=get_settings(),
        price_provider=MockPriceProvider(),
    )
    snap = await sched._snapshot(_candidate())
    assert snap is not None
    assert snap.last == 10.05  # from the provider — ibkr is None


@pytest.mark.integration
async def test_cycle_without_ibkr_produces_decision_skips_execution(db_session, tmp_path):
    """No broker: the decision is still produced; paper execution is skipped
    gracefully (not an error)."""
    from src.core.settings import get_settings

    discord = MockDiscord()
    sched = TradingScheduler(
        ibkr=None,
        executor=None,
        engine=MockEngine(_req()),
        discord=discord,
        kill_switch=KillSwitch(tmp_path / "k.flag"),
        settings=get_settings(),
        price_provider=MockPriceProvider(),
    )
    summary = await sched.run_daily_cycle(db_session, [_candidate()], 100_000)
    assert summary.decisions == ["t1"]  # decision produced
    assert summary.submitted == [] and summary.pending_approval == []  # not executed
    assert summary.execution_skipped == 1
    assert discord.events == []  # no execution-side alerts


@pytest.mark.integration
async def test_baseline_persists_when_zero_trades_submitted(db_session, db_engine, tmp_path):
    """Daily baseline must be committed even when no trade is submitted, so the
    daily-loss safeguard survives across cycles (Step-11 dry-run bug). Here the
    price provider finds no price ⇒ the candidate is skipped, zero decisions."""
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.core.settings import get_settings
    from src.trading.safeguards import KEY_DAILY_BASELINE, SystemStateStore

    discord = MockDiscord()
    sched = TradingScheduler(
        ibkr=MockIbkr(),
        executor=MockExecutor("SUBMITTED"),
        engine=MockEngine(_req()),
        discord=discord,
        kill_switch=KillSwitch(tmp_path / "k.flag"),
        settings=get_settings(),
        price_provider=MockNoPriceProvider(),
    )
    summary = await sched.run_daily_cycle(db_session, [_candidate()], 1_000_000)
    assert summary.submitted == [] and summary.pending_approval == []  # nothing traded
    assert summary.decisions == []  # no price ⇒ no decision

    # A FRESH session must see the committed baseline.
    async with AsyncSession(db_engine, expire_on_commit=False) as fresh:
        val = await SystemStateStore(fresh).get(KEY_DAILY_BASELINE)
    assert val is not None
    assert float(val) == 1_000_000.0


async def _seed_scored_deal(session, juridiction, ref, quality_flag=None, resolution_flag=None):
    from datetime import UTC, date, datetime
    from decimal import Decimal

    from src.core.models import Deal, Score

    deal = Deal(
        juridiction=juridiction,
        regulator_ref=ref,
        target_name=f"T-{ref}",
        acquirer_name="ACQ",
        announcement_date=date(2026, 5, 1),
        deal_type="opa",
        status="announced",
    )
    if quality_flag is not None:
        deal.offer_price_quality_flag = quality_flag
    if resolution_flag is not None:
        deal.ticker_resolution_flag = resolution_flag
    session.add(deal)
    await session.flush()
    session.add(
        Score(
            deal_id=deal.id,
            p_completion=Decimal("0.9"),
            decision="enter",
            model_version="v1",
            features={},
            score_stars=5,
            risk_factors=[],
            positive_factors=[],
            ts=datetime.now(tz=UTC),
        )
    )
    await session.flush()
    return deal.id


@pytest.mark.integration
async def test_load_candidates_respects_allowed_jurisdictions(db_session):
    from src.trading.scheduler import load_candidates
    from src.trading.ticker_resolver import TickerResolver

    await _seed_scored_deal(db_session, "DE", "BAFIN-DE000CBK1001-20260505")
    await _seed_scored_deal(db_session, "FR", "226C0538")
    await _seed_scored_deal(db_session, "IT", "IT-001")

    cands = await load_candidates(
        db_session, TickerResolver({}), min_stars=3, allowed_jurisdictions=["DE"]
    )
    assert len(cands) == 1
    assert {c.juridiction for c in cands} == {"DE"}


@pytest.mark.integration
async def test_load_candidates_returns_empty_when_no_matching_jurisdiction(db_session):
    from src.trading.scheduler import load_candidates
    from src.trading.ticker_resolver import TickerResolver

    # Only a DE deal exists; scoping to FR (valid enum, no rows) ⇒ empty.
    await _seed_scored_deal(db_session, "DE", "BAFIN-DE000CBK1001-20260505")
    cands = await load_candidates(
        db_session, TickerResolver({}), min_stars=3, allowed_jurisdictions=["FR"]
    )
    assert cands == []


class _FakeOpenFIGI:
    """Resolves any ISIN to a fixed home_venue result (no HTTP)."""

    def __init__(self):
        self.calls = []

    def resolve_isin_to_yahoo_ticker(self, isin):
        from src.pricing.openfigi_resolver import OpenFIGISource, YahooTickerResult

        self.calls.append(isin)
        return YahooTickerResult(
            isin=isin,
            yahoo_ticker="COVH.PA",
            exch_code_bbg="FP",
            figi="FIGI",
            source=OpenFIGISource.HOME_VENUE,
        )


@pytest.mark.integration
async def test_load_candidates_resolves_and_persists_ticker(db_session):
    """A fresh deal with an ISIN is resolved via OpenFIGI, the ticker persisted,
    and the candidate's yahoo_ticker is read back from the DB column."""
    from src.core.models import Deal
    from src.trading.scheduler import load_candidates
    from src.trading.ticker_resolver import TickerResolver

    deal_id = await _seed_scored_deal(db_session, "FR", "226C0900")
    deal = await db_session.get(Deal, deal_id)
    deal.ticker_target = "FR0000060303"  # ISIN
    await db_session.flush()

    figi = _FakeOpenFIGI()
    cands = await load_candidates(
        db_session, TickerResolver({}), min_stars=3, allowed_jurisdictions=["FR"], openfigi=figi
    )
    assert len(cands) == 1
    assert cands[0].yahoo_ticker == "COVH.PA"  # from persisted trading_ticker_yf
    assert figi.calls == ["FR0000060303"]

    # Persisted on the row + cache hit (no re-resolution) on a second pass.
    refreshed = await db_session.get(Deal, deal_id)
    assert refreshed.trading_ticker_yf == "COVH.PA"
    assert refreshed.ibkr_ticker == "COVH"
    assert refreshed.ibkr_exchange == "SBF"
    assert refreshed.ticker_resolution_flag == "home_venue"
    await load_candidates(
        db_session, TickerResolver({}), min_stars=3, allowed_jurisdictions=["FR"], openfigi=figi
    )
    assert figi.calls == ["FR0000060303"]  # still one call — already resolved


@pytest.mark.integration
async def test_confidence_gate_home_venue_strict_for_fr(db_session):
    """FR is gated: only home_venue is auto-tradable; growth / venue_fallback /
    premium_out_of_bounds → manual_review. DE is NOT gated (BaFin ISIN path)."""
    from src.trading.scheduler import load_candidates
    from src.trading.ticker_resolver import TickerResolver

    fr_home = await _seed_scored_deal(db_session, "FR", "FR-HOME", resolution_flag="home_venue")
    await _seed_scored_deal(db_session, "FR", "FR-GROWTH", resolution_flag="home_venue_growth")
    await _seed_scored_deal(db_session, "FR", "FR-FALLBACK", resolution_flag="venue_fallback")
    await _seed_scored_deal(db_session, "FR", "FR-PREMOOB", resolution_flag="premium_out_of_bounds")
    await _seed_scored_deal(db_session, "FR", "FR-NOMATCH", resolution_flag="no_match")
    de_home = await _seed_scored_deal(db_session, "DE", "DE-HOME", resolution_flag="home_venue")
    de_null = await _seed_scored_deal(db_session, "DE", "DE-NULL")  # flag NULL — DE not gated

    cands = await load_candidates(
        db_session,
        TickerResolver({}),
        min_stars=3,
        allowed_jurisdictions=["DE", "FR"],
        home_venue_strict_jurisdictions=["FR"],
    )
    ids = {c.deal_id for c in cands}
    assert fr_home in ids  # FR home_venue → tradable
    assert de_home in ids and de_null in ids  # DE unchanged (gated set excludes DE)
    # The only non-DE candidate left is the FR home_venue deal.
    assert {c.juridiction for c in cands if c.deal_id not in (de_home, de_null)} == {"FR"}
    assert len(ids) == 3  # FR-HOME + DE-HOME + DE-NULL only


@pytest.mark.integration
async def test_confidence_gate_excludes_it_via_allowed_jurisdictions(db_session):
    """IT (no ISIN ⇒ no_match) is excluded upstream by allowed_jurisdictions —
    it never reaches the FR-specific confidence gate."""
    from src.trading.scheduler import load_candidates
    from src.trading.ticker_resolver import TickerResolver

    await _seed_scored_deal(db_session, "IT", "IT-1", resolution_flag="no_match")
    cands = await load_candidates(
        db_session,
        TickerResolver({}),
        min_stars=3,
        allowed_jurisdictions=["DE", "FR"],
        home_venue_strict_jurisdictions=["FR"],
    )
    assert cands == []


@pytest.mark.integration
async def test_load_candidates_excludes_untradeable_offer_price_flag(db_session):
    from src.trading.scheduler import load_candidates
    from src.trading.ticker_resolver import TickerResolver

    # A verified_cash deal is tradable; a suspect_mixed deal (no scalar price)
    # must be excluded at the query level, not just skipped later on NULL price.
    keep = await _seed_scored_deal(db_session, "DE", "BAFIN-KEEP", quality_flag="verified_cash")
    mixed = await _seed_scored_deal(db_session, "DE", "BAFIN-MIXED", quality_flag="suspect_mixed")

    cands = await load_candidates(
        db_session, TickerResolver({}), min_stars=3, allowed_jurisdictions=["DE"]
    )
    ids = {c.deal_id for c in cands}
    assert keep in ids
    assert mixed not in ids
