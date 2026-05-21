"""Integration tests for src.dashboard.data — live DB queries with seeded fixtures."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.dashboard.data import (
    DealsFilters,
    _apply_filters,
    get_all_clusters,
    get_calibration_data,
    get_cluster_detail,
    get_events_for_cluster,
    get_feature_importance,
    get_filter_options,
    get_latest_model_metadata,
    get_pipeline_timeline,
    get_score_for_cluster,
    reset_engine_cache,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_engine(monkeypatch: pytest.MonkeyPatch, integration_db_url: str):  # type: ignore[no-untyped-def]
    """Point DATABASE_URL at the integration test DB (the autouse
    `_set_test_env` fixture in conftest defaults it to a dummy)."""
    monkeypatch.setenv("DATABASE_URL", integration_db_url)
    from src.core.settings import get_settings

    get_settings.cache_clear()
    reset_engine_cache()
    yield
    # Tear down explicitly so the connection is closed before the next test.
    reset_engine_cache()


async def _seed(session, **kw) -> int:  # type: ignore[no-untyped-def]
    """Insert a Deal + matching Score row, return the deal_id."""
    from src.core.models import Deal, Score

    deal = Deal(
        juridiction=kw.get("juridiction", "FR"),
        regulator_ref=kw["regulator_ref"],
        target_name=kw.get("target_name", "TARGET"),
        acquirer_name=kw.get("acquirer_name", "BIDDER"),
        announcement_date=kw.get("announcement_date", date(2025, 6, 1)),
        deal_type=kw.get("deal_type", "opa"),
        status=kw.get("status", "announced"),
        completion_label=kw.get("completion_label"),
    )
    session.add(deal)
    await session.flush()
    session.add(
        Score(
            deal_id=deal.id,
            p_completion=Decimal(str(kw.get("p_completion", 0.85))),
            decision=kw.get("decision", "enter"),
            model_version=kw.get("model_version", "scoring_test_v1"),
            features=kw.get("features", {"acquirer_type": "corporate"}),
            score_stars=kw.get("score_stars", 5),
            risk_factors=kw.get("risk_factors", []),
            positive_factors=kw.get("positive_factors", []),
            ts=kw.get("ts", datetime.now(tz=UTC)),
        )
    )
    await session.commit()
    return deal.id


async def test_get_all_clusters_returns_scored_rows(db_session) -> None:  # type: ignore[no-untyped-def]
    deal_id = await _seed(db_session, regulator_ref="AMF-DASH-001", target_name="ALPHA SA")
    df = get_all_clusters(DealsFilters(jurisdictions=("FR",)))
    assert not df.empty
    assert deal_id in df["cluster_id"].tolist()
    assert "p_completion" in df.columns
    assert "score_stars" in df.columns


async def test_get_all_clusters_filters_by_jurisdiction(db_session) -> None:  # type: ignore[no-untyped-def]
    await _seed(db_session, regulator_ref="AMF-DASH-002", target_name="ALPHA", juridiction="FR")
    await _seed(db_session, regulator_ref="CONSOB-DASH-001", target_name="BETA", juridiction="IT")
    fr = get_all_clusters(DealsFilters(jurisdictions=("FR",)))
    it = get_all_clusters(DealsFilters(jurisdictions=("IT",)))
    assert all(fr["juridiction"] == "FR")
    assert all(it["juridiction"] == "IT")


async def test_get_all_clusters_filters_by_status_pending(db_session) -> None:  # type: ignore[no-untyped-def]
    await _seed(db_session, regulator_ref="P1", target_name="PENDING", completion_label=None)
    await _seed(db_session, regulator_ref="P2", target_name="CLOSED", completion_label=1)
    pending = get_all_clusters(DealsFilters(status="pending"))
    closed = get_all_clusters(DealsFilters(status="closed"))
    assert "PENDING" in pending["target_name"].tolist()
    assert "PENDING" not in closed["target_name"].tolist()
    assert "CLOSED" in closed["target_name"].tolist()


async def test_get_all_clusters_filters_by_stars(db_session) -> None:  # type: ignore[no-untyped-def]
    await _seed(db_session, regulator_ref="S5", target_name="FIVESTAR", score_stars=5)
    await _seed(db_session, regulator_ref="S2", target_name="TWOSTAR", score_stars=2)
    high = get_all_clusters(DealsFilters(stars=(5,)))
    low = get_all_clusters(DealsFilters(stars=(2,)))
    assert "FIVESTAR" in high["target_name"].tolist()
    assert "TWOSTAR" in low["target_name"].tolist()
    assert "FIVESTAR" not in low["target_name"].tolist()


async def test_get_cluster_detail_returns_siblings_for_multi_stage(db_session) -> None:  # type: ignore[no-untyped-def]
    """An FR target with 3 BDIF filings — detail returns 3 siblings."""
    from src.core.models import Deal

    representative_id = await _seed(
        db_session, regulator_ref="MS-001", target_name="MULTISTAGE", deal_type="opa"
    )
    # Add 2 more sibling deals (no scores needed for these — siblings come from `deals` only)
    for i in range(2):
        db_session.add(
            Deal(
                juridiction="FR",
                regulator_ref=f"MS-00{i + 2}",
                target_name="MULTISTAGE",
                acquirer_name="BIDDER",
                announcement_date=date(2025, 6, 1),
                deal_type="opr",
                status="announced",
            )
        )
    await db_session.commit()

    detail = get_cluster_detail(representative_id)
    assert detail is not None
    assert detail["target_name"] == "MULTISTAGE"
    assert len(detail["siblings"]) == 3


async def test_get_cluster_detail_returns_none_for_unknown(db_session) -> None:  # type: ignore[no-untyped-def]
    assert get_cluster_detail(999_999_999) is None


async def test_get_score_for_cluster_returns_latest(db_session) -> None:  # type: ignore[no-untyped-def]
    cid = await _seed(db_session, regulator_ref="SCORE-1", target_name="X")
    out = get_score_for_cluster(cid)
    assert out is not None
    assert out["deal_id"] == cid
    assert out["model_version"] == "scoring_test_v1"


async def test_get_events_for_cluster_aggregates_chain(db_session) -> None:  # type: ignore[no-untyped-def]
    from src.core.models import Event

    cid = await _seed(db_session, regulator_ref="EV-1", target_name="EVTARGET")
    db_session.add(
        Event(
            deal_id=cid,
            ts=datetime.now(tz=UTC),
            event_type="filing_amf",
            description="test event",
        )
    )
    await db_session.commit()

    events = get_events_for_cluster(cid)
    assert len(events) == 1
    assert events[0]["event_type"] == "filing_amf"


async def test_get_calibration_data_returns_bins_for_labelled_clusters(  # type: ignore[no-untyped-def]
    db_session,
) -> None:
    await _seed(
        db_session,
        regulator_ref="CAL-1",
        target_name="CAL_A",
        completion_label=1,
        p_completion=0.95,
    )
    await _seed(
        db_session,
        regulator_ref="CAL-2",
        target_name="CAL_B",
        completion_label=0,
        p_completion=0.35,
    )
    df = get_calibration_data()
    assert not df.empty
    assert {"bin_mid", "empirical_rate", "n"}.issubset(df.columns)


async def test_get_pipeline_timeline_groups_by_month(db_session) -> None:  # type: ignore[no-untyped-def]
    await _seed(
        db_session,
        regulator_ref="PT-1",
        target_name="PT_A",
        announcement_date=date(2025, 6, 5),
    )
    await _seed(
        db_session,
        regulator_ref="PT-2",
        target_name="PT_B",
        announcement_date=date(2025, 6, 25),
    )
    df = get_pipeline_timeline()
    assert "month" in df.columns
    assert "n" in df.columns


async def test_get_filter_options_returns_distinct_lists(db_session) -> None:  # type: ignore[no-untyped-def]
    await _seed(db_session, regulator_ref="OPT-1", target_name="OPT_A", juridiction="FR")
    await _seed(db_session, regulator_ref="OPT-2", target_name="OPT_B", juridiction="IT")
    opts = get_filter_options()
    assert {"jurisdictions", "deal_types", "acquirer_types"} == set(opts.keys())
    assert "FR" in opts["jurisdictions"]
    assert "IT" in opts["jurisdictions"]


async def test_get_latest_model_metadata_returns_summary(db_session) -> None:  # type: ignore[no-untyped-def]
    await _seed(db_session, regulator_ref="META-1", target_name="META_A")
    md = get_latest_model_metadata()
    assert "model_version" in md
    assert "n_scored" in md


async def test_get_feature_importance_returns_empty_when_no_model(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # No PKL in tmp_path → empty frame
    df = get_feature_importance(model_path=tmp_path / "missing.pkl")
    assert df.empty or len(df) == 0


# --------------------------- _apply_filters unit tests ---------------------------


def test_apply_filters_no_filters_returns_empty_clauses() -> None:
    sql, params = _apply_filters("SELECT 1 WHERE x = 1", DealsFilters())
    # No clauses added, SQL unchanged
    assert "AND" not in sql or sql.endswith("WHERE x = 1")
    assert params == {}


def test_apply_filters_status_pending_emits_is_null() -> None:
    sql, params = _apply_filters("SELECT 1 WHERE 1=1", DealsFilters(status="pending"))
    assert "completion_label IS NULL" in sql


def test_apply_filters_status_closed_emits_equals_one() -> None:
    sql, _ = _apply_filters("SELECT 1 WHERE 1=1", DealsFilters(status="closed"))
    assert "completion_label = 1" in sql


def test_apply_filters_status_failed_emits_equals_zero() -> None:
    sql, _ = _apply_filters("SELECT 1 WHERE 1=1", DealsFilters(status="failed"))
    assert "completion_label = 0" in sql


def test_apply_filters_combines_multiple() -> None:
    f = DealsFilters(
        jurisdictions=("FR",),
        stars=(4, 5),
        status="pending",
        date_from=date(2024, 1, 1),
    )
    sql, params = _apply_filters("SELECT 1 WHERE 1=1", f)
    assert "ANY(:jurs)" in sql
    assert "ANY(:stars)" in sql
    assert "completion_label IS NULL" in sql
    assert "date_from" in params
    assert params["jurs"] == ["FR"]
    assert params["stars"] == [4, 5]


def test_dealsfilters_with_defaults_fills_date_range() -> None:
    f = DealsFilters().with_defaults()
    assert f.date_from is not None
    assert f.date_to is not None
    assert f.stars == (3, 4, 5)
