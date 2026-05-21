"""Integration tests for the Phase-8 trading data layer (read-only, live DB)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.dashboard.data import (
    get_live_positions,
    get_rampup_status,
    get_realized_pnl_series,
    get_recent_trades,
    get_trading_kpis,
    reset_engine_cache,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_engine(monkeypatch: pytest.MonkeyPatch, integration_db_url: str):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DATABASE_URL", integration_db_url)
    from src.core.settings import get_settings

    get_settings.cache_clear()
    reset_engine_cache()
    yield
    reset_engine_cache()


async def _seed(session):  # type: ignore[no-untyped-def]
    from src.core.models import Deal, PaperPosition, SystemState, Trade

    deal = Deal(
        juridiction="DE",
        regulator_ref="BAFIN-DE000CBK1001-20260505",
        target_name="Commerzbank",
        acquirer_name="UniCredit",
        announcement_date=date(2026, 5, 5),
        deal_type="opa",
        status="announced",
    )
    session.add(deal)
    await session.flush()

    session.add(
        Trade(
            trade_id="trade-1",
            deal_id=deal.id,
            side="BUY",
            quantity=100,
            limit_price=Decimal("10.0"),
            status="FILLED",
            filled_price=Decimal("10.0"),
            pnl_realized=Decimal("0"),
            created_at=datetime(2026, 5, 6, 9, 0, tzinfo=UTC),
        )
    )
    session.add(
        PaperPosition(
            deal_id=deal.id,
            entry_price=Decimal("10.0"),
            size_eur=Decimal("1000.0"),
            side="long",
            status="open",
        )
    )
    session.add(
        PaperPosition(
            deal_id=deal.id,
            entry_price=Decimal("10.0"),
            exit_price=Decimal("11.0"),
            size_eur=Decimal("1000.0"),
            side="long",
            status="closed",
            pnl_eur=Decimal("100.0"),
            close_ts=datetime(2026, 5, 7, 16, 0, tzinfo=UTC),
        )
    )
    session.add(SystemState(key="rampup_trades_validated", value="2"))
    await session.commit()
    return deal.id


async def test_live_positions(db_session):
    await _seed(db_session)
    df = get_live_positions()
    assert len(df) == 1  # only the open one
    assert df.iloc[0]["target_name"] == "Commerzbank"
    assert float(df.iloc[0]["size_eur"]) == 1000.0


async def test_recent_trades(db_session):
    await _seed(db_session)
    df = get_recent_trades()
    assert len(df) == 1
    assert df.iloc[0]["trade_id"] == "trade-1"
    assert df.iloc[0]["status"] == "FILLED"
    assert df.iloc[0]["target_name"] == "Commerzbank"


async def test_rampup_status(db_session):
    await _seed(db_session)
    status = get_rampup_status()
    assert status["validated"] == 2
    assert status["required"] >= 1


async def test_rampup_status_defaults_to_zero(db_session):
    # no system_state row
    status = get_rampup_status()
    assert status["validated"] == 0


async def test_trading_kpis(db_session):
    await _seed(db_session)
    kpis = get_trading_kpis()
    assert int(kpis["open_positions"]) == 1
    assert int(kpis["filled"]) == 1


async def test_realized_pnl_series(db_session):
    await _seed(db_session)
    df = get_realized_pnl_series()
    assert len(df) == 1  # one closed position day
    assert float(df.iloc[0]["realized"]) == 100.0
    assert float(df.iloc[0]["cumulative"]) == 100.0
