"""Unit tests for src.scoring.features — heuristics + cluster aggregation."""

from __future__ import annotations

import math
from datetime import date

import pytest

from src.scoring.features import (
    BOOLEAN_FEATURES,
    CATEGORICAL_FEATURES,
    FEATURE_NAMES,
    NUMERIC_FEATURES,
    _classify_acquirer,
    _classify_payment,
    _fdi_risk,
    _is_cross_border,
    features_to_vector,
)


def _stub_deal(**kw):  # type: ignore[no-untyped-def]
    from types import SimpleNamespace

    defaults = {
        "deal_type": "opa",
        "premium_pct": None,
        "min_acceptance_threshold": None,
        "expected_close_date": None,
        "announcement_date": date(2025, 1, 1),
        "completion_label": None,
        "id": 1,
        "target_name": "X",
        "acquirer_name": "Y",
        "juridiction": "FR",
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_feature_names_unique_and_covered() -> None:
    """No duplicates between the three buckets; the full list is the union."""
    assert len(FEATURE_NAMES) == len(NUMERIC_FEATURES) + len(CATEGORICAL_FEATURES) + len(
        BOOLEAN_FEATURES
    )
    assert set(FEATURE_NAMES) == set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES) | set(
        BOOLEAN_FEATURES
    )


@pytest.mark.parametrize(
    ("acquirer", "expected"),
    [
        ("UniCredit S.p.A", "corporate"),
        ("KKR Elbe BidCo AG", "pe"),
        ("ADNOC International Germany Holding AG", "soe"),
        ("Banca CF+ Credito Fondiario Spa", "corporate"),
        ("Christian Bouygues", "family"),
    ],
)
def test_classify_acquirer(acquirer: str, expected: str) -> None:
    assert _classify_acquirer(acquirer) == expected


def test_classify_acquirer_unknown_on_empty_string() -> None:
    assert _classify_acquirer("") == "unknown"


@pytest.mark.parametrize(
    ("target", "acquirer", "expected"),
    [
        ("COMMERZBANK Aktiengesellschaft", "UniCredit S.p.A , Italien", True),
        ("Banca Sistema Spa", "Banca CF+ Credito Fondiario Spa", False),
        ("PSI Software SE", "Zest Bidco GmbH", False),  # both German
        # ADNOC Abu Dhabi parent → cross-border
        ("Covestro AG", "ADNOC Abu Dhabi Holding", True),
        # Known V1 false positive: acquirer is a German wrapper of a UAE
        # parent. Heuristic flags any token mismatch as cross-border —
        # a more accurate signal would need country-of-incorporation
        # data (phase 8+).
        ("Covestro AG", "ADNOC International Germany Holding AG", True),
    ],
)
def test_is_cross_border(target: str, acquirer: str, expected: bool) -> None:
    assert _is_cross_border(target, acquirer) is expected


@pytest.mark.parametrize(
    ("acquirer", "expected"),
    [
        ("ADNOC International Germany Holding AG", True),
        ("JINGDONG HOLDING GERMANY GMBH", True),  # JD.com
        ("UniCredit S.p.A", False),
        ("KKR Elbe BidCo AG", False),
    ],
)
def test_fdi_risk(acquirer: str, expected: bool) -> None:
    assert _fdi_risk(acquirer) is expected


def test_classify_payment_distinguishes_exchange_offers() -> None:
    assert _classify_payment(_stub_deal(deal_type="opa")) == "cash"
    assert _classify_payment(_stub_deal(deal_type="ope")) == "stock"
    assert _classify_payment(_stub_deal(deal_type="opas")) == "stock"


def test_features_to_vector_handles_nan_booleans_and_categoricals() -> None:
    raw = {
        "bid_premium_pct": float("nan"),
        "relative_size": 1.5,
        "min_acceptance_threshold": None,
        "days_to_expected_close": 90.0,
        "events_count": 3,
        "deal_type": "opa",
        "payment_type": "cash",
        "jurisdiction": "FR",
        "target_sector": None,
        "acquirer_type": "corporate",
        "cross_border": True,
        "has_irrevocable_undertaking": False,
        "fdi_risk_flag": True,
    }
    v = features_to_vector(raw)
    assert math.isnan(float(v["bid_premium_pct"]))
    assert math.isnan(float(v["min_acceptance_threshold"]))
    assert v["relative_size"] == 1.5
    assert v["events_count"] == 3.0
    assert v["target_sector"] == "unknown"  # None → unknown
    assert v["cross_border"] == 1.0
    assert v["has_irrevocable_undertaking"] == 0.0
    assert v["fdi_risk_flag"] == 1.0


# ---------------------------- DB integration ----------------------------


pytestmark_integration = pytest.mark.integration


@pytest.mark.integration
async def test_extract_cluster_features_aggregates_fr_chain(db_session) -> None:  # type: ignore[no-untyped-def]
    """An FR multi-stage chain (same target across 3 BDIF rows) yields
    one cluster with events_count=3 and the first-stage deal_type."""
    from src.core.models import Deal
    from src.scoring.features import extract_cluster_features

    deals = [
        Deal(
            juridiction="FR",
            regulator_ref=f"AMF-TEST-{i:03d}",
            target_name="TESTCO",
            acquirer_name="BidCo SARL",
            announcement_date=date(2025, 1, 1 + i),
            deal_type=("opa" if i == 0 else "opr"),
            status="announced",
        )
        for i in range(3)
    ]
    db_session.add_all(deals)
    await db_session.commit()

    cf = await extract_cluster_features("TESTCO", "FR", db_session)
    assert cf is not None
    assert cf.target_name == "TESTCO"
    assert cf.jurisdiction == "FR"
    assert cf.features["events_count"] == 3.0
    # First-stage deal_type wins
    assert cf.features["deal_type"] == "opa"
    # Acquirer 'BidCo SARL' is PE per heuristic
    assert cf.features["acquirer_type"] == "pe"
    # FR + 'SARL' marker in acquirer → cross-border True
    assert cf.features["cross_border"] is True
    # No label set on any row
    assert cf.label is None


@pytest.mark.integration
async def test_extract_cluster_features_propagates_label(db_session) -> None:  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime

    from src.core.models import Deal
    from src.scoring.features import extract_cluster_features

    deals = [
        Deal(
            juridiction="IT",
            regulator_ref="CONSOB-TEST-1",
            target_name="Pioneer Spa",
            acquirer_name="Acquirer Spa",
            announcement_date=date(2025, 6, 1),
            deal_type="opa_obligatoire",
            status="announced",
            completion_label=0,
            completion_label_source="news.example",
            completion_label_date=datetime.now(tz=UTC),
        )
    ]
    db_session.add_all(deals)
    await db_session.commit()

    cf = await extract_cluster_features("Pioneer Spa", "IT", db_session)
    assert cf is not None
    assert cf.label == 0
