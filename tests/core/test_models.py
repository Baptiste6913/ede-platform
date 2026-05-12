"""CRUD + constraint tests against a real PostgreSQL + TimescaleDB.

Each table gets at least 3 tests: insert/read, update, delete. Plus:
- one cascade-delete test (deleting a deal nukes its events/scores/...)
- one unique-constraint test (deals(juridiction, regulator_ref))
- TimescaleDB hypertable presence test
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    Analysis,
    Deal,
    Event,
    PaperPosition,
    Price,
    Score,
)
from tests.fixtures.seed_deals import SEED_DEALS, expected_count_by_jurisdiction

pytestmark = pytest.mark.integration


# =========================================================================
# helpers
# =========================================================================


async def _persist(session: AsyncSession, obj: Any) -> Any:
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def _seed_one_deal(session: AsyncSession, **overrides: Any) -> Deal:
    base = dict(SEED_DEALS[0])
    base.update(overrides)
    return await _persist(session, Deal(**base))


# =========================================================================
# deals — 4 tests (CRUD + unique)
# =========================================================================


async def test_deals_insert_and_read_back(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    assert deal.id is not None
    assert deal.created_at is not None
    assert deal.updated_at is not None

    fetched = (await db_session.execute(select(Deal).where(Deal.id == deal.id))).scalar_one()
    assert fetched.juridiction == "FR"
    assert fetched.regulator_ref == SEED_DEALS[0]["regulator_ref"]
    assert fetched.offer_price == Decimal("28.50")


async def test_deals_update_status_persists(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    deal.status = "closed"
    await db_session.commit()

    fetched = (await db_session.execute(select(Deal).where(Deal.id == deal.id))).scalar_one()
    assert fetched.status == "closed"


async def test_deals_delete_removes_row(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    await db_session.delete(deal)
    await db_session.commit()

    result = (await db_session.execute(select(Deal).where(Deal.id == deal.id))).scalar_one_or_none()
    assert result is None


async def test_deals_unique_juridiction_regulator_ref(db_session: AsyncSession) -> None:
    await _seed_one_deal(db_session)
    with pytest.raises(IntegrityError):
        await _seed_one_deal(db_session)  # exact same juridiction + regulator_ref


async def test_seed_distribution_matches_brief(db_session: AsyncSession) -> None:
    """Bulk insert all 10 seed deals and assert FR/IT/DE distribution."""
    for d in SEED_DEALS:
        db_session.add(Deal(**d))
    await db_session.commit()
    assert expected_count_by_jurisdiction() == {"FR": 3, "IT": 3, "DE": 4}
    rows = (await db_session.execute(select(Deal))).scalars().all()
    assert len(rows) == 10


# =========================================================================
# events — 3 tests
# =========================================================================


async def test_events_insert_and_read(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    evt = Event(
        deal_id=deal.id,
        ts=datetime.now(tz=UTC),
        event_type="filing_amf",
        description="initial AMF filing",
        raw_payload={"ref": deal.regulator_ref, "pages": 87},
    )
    await _persist(db_session, evt)

    fetched = (await db_session.execute(select(Event).where(Event.id == evt.id))).scalar_one()
    assert fetched.event_type == "filing_amf"
    assert fetched.raw_payload == {"ref": deal.regulator_ref, "pages": 87}


async def test_events_jsonb_supports_partial_update(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    evt = Event(
        deal_id=deal.id,
        ts=datetime.now(tz=UTC),
        event_type="clearance",
        raw_payload={"authority": "DG_COMP", "phase": "1"},
    )
    await _persist(db_session, evt)
    evt.raw_payload = {**(evt.raw_payload or {}), "phase": "2"}
    await db_session.commit()

    fetched = (await db_session.execute(select(Event).where(Event.id == evt.id))).scalar_one()
    assert fetched.raw_payload == {"authority": "DG_COMP", "phase": "2"}


async def test_events_cascade_delete_with_deal(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    for et in ("filing_amf", "clearance", "extension"):
        db_session.add(
            Event(
                deal_id=deal.id,
                ts=datetime.now(tz=UTC),
                event_type=et,
            )
        )
    await db_session.commit()

    rows = (await db_session.execute(select(Event).where(Event.deal_id == deal.id))).scalars().all()
    assert len(rows) == 3

    await db_session.delete(deal)
    await db_session.commit()

    rows_after = (
        (await db_session.execute(select(Event).where(Event.deal_id == deal.id))).scalars().all()
    )
    assert rows_after == []


# =========================================================================
# scores — 3 tests
# =========================================================================


async def test_scores_insert_decision_and_features(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    score = Score(
        deal_id=deal.id,
        p_completion=Decimal("0.82345"),
        p_market_implied=Decimal("0.75000"),
        edge=Decimal("0.07345"),
        expected_return_annualized=Decimal("0.21500"),
        decision="enter",
        model_version="v0_2026_05_12",
        features={
            "bid_premium_pct": 0.18,
            "attitude_hostile": False,
            "payment_cash_share": 1.0,
        },
    )
    await _persist(db_session, score)
    fetched = (await db_session.execute(select(Score).where(Score.id == score.id))).scalar_one()
    assert fetched.decision == "enter"
    assert fetched.features is not None
    assert fetched.features["bid_premium_pct"] == 0.18


async def test_scores_p_completion_check_constraint(
    db_session: AsyncSession,
) -> None:
    deal = await _seed_one_deal(db_session)
    bad = Score(
        deal_id=deal.id,
        p_completion=Decimal("1.5"),  # violates check
        decision="skip",
        model_version="v0",
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_scores_history_for_a_deal(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    base = datetime.now(tz=UTC)
    for i, p in enumerate([Decimal("0.5"), Decimal("0.6"), Decimal("0.7")]):
        db_session.add(
            Score(
                deal_id=deal.id,
                ts=base + timedelta(hours=i),
                p_completion=p,
                decision="wait" if p < Decimal("0.7") else "enter",
                model_version="v0",
            )
        )
    await db_session.commit()
    rows = (
        (await db_session.execute(select(Score).where(Score.deal_id == deal.id).order_by(Score.ts)))
        .scalars()
        .all()
    )
    assert [r.p_completion for r in rows] == [
        Decimal("0.50000"),
        Decimal("0.60000"),
        Decimal("0.70000"),
    ]


# =========================================================================
# analyses — 3 tests
# =========================================================================


async def test_analyses_insert_with_jsonb_lists(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    analysis = Analysis(
        deal_id=deal.id,
        source="claude_opus_4_7",
        brief_path=f"/obsidian/EDE/Briefs/2026-05-12_{deal.ticker_target}.md",
        verdict="GO",
        thesis_md="## Thesis\nStrong bid premium, regulatory path clear.",
        risks=[{"label": "antitrust SO", "severity": "med"}],
        catalysts=[{"label": "clearance expected", "date": "2025-01-15"}],
    )
    await _persist(db_session, analysis)
    fetched = (
        await db_session.execute(select(Analysis).where(Analysis.id == analysis.id))
    ).scalar_one()
    assert fetched.verdict == "GO"
    assert fetched.risks is not None
    assert fetched.risks[0]["label"] == "antitrust SO"


async def test_analyses_update_verdict(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    a = Analysis(deal_id=deal.id, source="manual", verdict="WAIT")
    await _persist(db_session, a)
    a.verdict = "GO"
    await db_session.commit()
    fetched = (await db_session.execute(select(Analysis).where(Analysis.id == a.id))).scalar_one()
    assert fetched.verdict == "GO"


async def test_analyses_cascade_delete(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    db_session.add(Analysis(deal_id=deal.id, source="manual", verdict="SKIP"))
    await db_session.commit()
    await db_session.delete(deal)
    await db_session.commit()
    rows = (
        (await db_session.execute(select(Analysis).where(Analysis.deal_id == deal.id)))
        .scalars()
        .all()
    )
    assert rows == []


# =========================================================================
# paper_positions — 3 tests
# =========================================================================


async def test_positions_open_and_close(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    pos = PaperPosition(
        deal_id=deal.id,
        entry_price=Decimal("28.00"),
        size_eur=Decimal("5000.00"),
        side="long",
        status="open",
    )
    await _persist(db_session, pos)

    pos.exit_price = Decimal("28.50")
    pos.pnl_eur = Decimal("89.29")
    pos.status = "closed"
    pos.close_ts = datetime.now(tz=UTC)
    await db_session.commit()

    fetched = (
        await db_session.execute(select(PaperPosition).where(PaperPosition.id == pos.id))
    ).scalar_one()
    assert fetched.status == "closed"
    assert fetched.pnl_eur == Decimal("89.29")


async def test_positions_size_must_be_positive(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    bad = PaperPosition(
        deal_id=deal.id,
        entry_price=Decimal("10.0"),
        size_eur=Decimal("0.0"),  # violates check
        side="long",
        status="open",
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_positions_cascade_delete_with_deal(db_session: AsyncSession) -> None:
    deal = await _seed_one_deal(db_session)
    for _ in range(2):
        db_session.add(
            PaperPosition(
                deal_id=deal.id,
                entry_price=Decimal("28.0"),
                size_eur=Decimal("1000.0"),
                side="long",
                status="open",
            )
        )
    await db_session.commit()

    await db_session.delete(deal)
    await db_session.commit()
    rows = (
        (await db_session.execute(select(PaperPosition).where(PaperPosition.deal_id == deal.id)))
        .scalars()
        .all()
    )
    assert rows == []


# =========================================================================
# prices (TimescaleDB hypertable) — 3 tests
# =========================================================================


async def test_prices_is_a_hypertable(db_session: AsyncSession) -> None:
    """Verify the prices table is registered as a TimescaleDB hypertable."""
    result = await db_session.execute(
        text(
            "SELECT hypertable_name FROM timescaledb_information.hypertables "
            "WHERE hypertable_name = 'prices'"
        )
    )
    rows = result.scalars().all()
    assert rows == ["prices"]


async def test_prices_insert_ohlcv(db_session: AsyncSession) -> None:
    now = datetime.now(tz=UTC).replace(microsecond=0)
    p = Price(
        ticker="ALGOL.PA",
        ts=now,
        open=Decimal("28.00"),
        high=Decimal("28.60"),
        low=Decimal("27.90"),
        close=Decimal("28.50"),
        volume=123456,
        source="ibkr",
    )
    await _persist(db_session, p)
    fetched = (
        await db_session.execute(
            select(Price).where(Price.ticker == "ALGOL.PA").where(Price.ts == now)
        )
    ).scalar_one()
    assert fetched.close == Decimal("28.50")


async def test_prices_continuous_aggregates_exist(db_session: AsyncSession) -> None:
    """Both 1h and 1d continuous aggregates must be registered."""
    result = await db_session.execute(
        text(
            "SELECT view_name FROM timescaledb_information.continuous_aggregates "
            "WHERE view_name IN ('prices_1h', 'prices_1d') "
            "ORDER BY view_name"
        )
    )
    names = result.scalars().all()
    assert names == ["prices_1d", "prices_1h"]
