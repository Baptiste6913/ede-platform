"""Tests for src.dashboard.paper_portfolio_mock — deterministic mock output."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.dashboard.data import reset_engine_cache
from src.dashboard.paper_portfolio_mock import (
    _DEFAULT_ENTRY_PRICE,
    _N_POSITIONS,
    _entry_price_from,
    _seeded_rng,
    build_mock_portfolio,
    build_mock_watchlist,
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


# ---------------------------- pure-function tests ----------------------------


def test_entry_price_from_uses_default_on_none() -> None:
    assert _entry_price_from(None) == _DEFAULT_ENTRY_PRICE


def test_entry_price_from_uses_default_on_nan() -> None:
    import math

    assert _entry_price_from(math.nan) == _DEFAULT_ENTRY_PRICE


def test_entry_price_from_discounts_offer_price_by_5pct() -> None:
    out = _entry_price_from(100.0)
    assert 94.99 < out < 95.01  # 100 * 0.95 = 95.0


def test_seeded_rng_is_deterministic_per_cluster() -> None:
    rng1 = _seeded_rng(42)
    rng2 = _seeded_rng(42)
    assert rng1.uniform() == rng2.uniform()


def test_seeded_rng_differs_across_clusters() -> None:
    a = _seeded_rng(1).uniform()
    b = _seeded_rng(99).uniform()
    assert a != b


# ---------------------------- DB-backed integration --------------------------


async def _seed(session, **kw) -> int:  # type: ignore[no-untyped-def]
    from src.core.models import Deal, Score

    deal = Deal(
        juridiction=kw.get("juridiction", "FR"),
        regulator_ref=kw["regulator_ref"],
        target_name=kw.get("target_name", "TARGET"),
        acquirer_name=kw.get("acquirer_name", "BIDDER"),
        announcement_date=kw.get("announcement_date", date(2025, 6, 1)),
        deal_type=kw.get("deal_type", "opa"),
        status=kw.get("status", "announced"),
    )
    session.add(deal)
    await session.flush()
    session.add(
        Score(
            deal_id=deal.id,
            p_completion=Decimal(str(kw.get("p_completion", 0.95))),
            decision="enter",
            model_version="scoring_test_v1",
            features=kw.get("features", {"acquirer_type": "corporate"}),
            score_stars=kw.get("score_stars", 5),
            risk_factors=[],
            positive_factors=[],
            ts=kw.get("ts", datetime.now(tz=UTC)),
        )
    )
    await session.commit()
    return deal.id


async def test_build_mock_portfolio_empty_when_no_5star(db_session) -> None:  # type: ignore[no-untyped-def]
    # No 5-star clusters seeded — portfolio should be empty but valid.
    portfolio = build_mock_portfolio()
    assert isinstance(portfolio.positions, list)
    assert portfolio.total_deployed_eur == 0.0
    assert portfolio.open_pnl_eur == 0.0
    # Metrics are constant placeholders for V1 mock.
    assert portfolio.metrics.sharpe_ratio == pytest.approx(1.42)


async def test_build_mock_portfolio_picks_top_n_5star_deals(db_session) -> None:  # type: ignore[no-untyped-def]
    # Seed 4 five-star deals → portfolio takes the top N (=3).
    for i in range(4):
        await _seed(
            db_session,
            regulator_ref=f"PORT-{i}",
            target_name=f"PORTCO_{i}",
            announcement_date=date(2025, 6, i + 1),
            score_stars=5,
        )
    portfolio = build_mock_portfolio()
    assert len(portfolio.positions) == _N_POSITIONS
    for p in portfolio.positions:
        assert p.stars == 5
        assert p.size_eur == pytest.approx(10000.0)
        assert p.entry_price > 0
        assert p.now_price > 0
    # Total = N positions x 10 000 EUR
    assert portfolio.total_deployed_eur == pytest.approx(30000.0)


async def test_build_mock_portfolio_is_deterministic_across_reloads(  # type: ignore[no-untyped-def]
    db_session,
) -> None:
    await _seed(
        db_session,
        regulator_ref="DET-1",
        target_name="DETCO",
        announcement_date=date(2025, 6, 1),
        score_stars=5,
    )
    first = build_mock_portfolio()
    second = build_mock_portfolio()
    if first.positions and second.positions:
        assert first.positions[0].pnl_eur == second.positions[0].pnl_eur
        assert first.positions[0].now_price == second.positions[0].now_price


async def test_build_mock_watchlist_returns_next_5star_after_portfolio(  # type: ignore[no-untyped-def]
    db_session,
) -> None:
    # Seed 6 five-star deals → portfolio takes 3, watchlist takes the next 5
    # (only 3 will be left after the portfolio).
    for i in range(6):
        await _seed(
            db_session,
            regulator_ref=f"WL-{i}",
            target_name=f"WLCO_{i}",
            announcement_date=date(2025, 6, i + 1),
            score_stars=5,
        )
    watch = build_mock_watchlist(limit=5)
    assert isinstance(watch, list)
    assert len(watch) == 3
    for entry in watch:
        assert entry["stars"] == 5
        assert "target" in entry
        assert "p_completion" in entry


async def test_build_mock_watchlist_empty_when_no_clusters(db_session) -> None:  # type: ignore[no-untyped-def]
    out = build_mock_watchlist(limit=5)
    assert out == []
