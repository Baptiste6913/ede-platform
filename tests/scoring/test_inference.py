"""Unit + integration tests for src.scoring.inference."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.scoring.inference import score_deal
from src.scoring.model import ScoringModel


def _quick_model() -> ScoringModel:
    rng = np.random.default_rng(seed=7)
    n_pos = 20
    n_neg = 6
    X = pd.DataFrame(
        {
            "bid_premium_pct": rng.normal(20, 4, n_pos + n_neg),
            "relative_size": rng.normal(1, 0.3, n_pos + n_neg),
            "min_acceptance_threshold": rng.normal(0.6, 0.05, n_pos + n_neg),
            "days_to_expected_close": rng.normal(60, 10, n_pos + n_neg),
            "events_count": rng.integers(2, 6, n_pos + n_neg).astype(float),
            "deal_type": ["opa"] * (n_pos + n_neg),
            "payment_type": ["cash"] * (n_pos + n_neg),
            "jurisdiction": ["FR"] * (n_pos + n_neg),
            "target_sector": ["unknown"] * (n_pos + n_neg),
            "acquirer_type": ["corporate"] * n_pos + ["family"] * n_neg,
            "cross_border": [0.0] * (n_pos + n_neg),
            "has_irrevocable_undertaking": [0.0] * (n_pos + n_neg),
            "fdi_risk_flag": [0.0] * (n_pos + n_neg),
        }
    )
    y = np.array([1] * n_pos + [0] * n_neg)
    m = ScoringModel(version="quick")
    m.fit(X, y)
    return m


@pytest.mark.integration
async def test_score_deal_returns_full_payload(db_session) -> None:  # type: ignore[no-untyped-def]
    from src.core.models import Deal

    deal = Deal(
        juridiction="FR",
        regulator_ref="AMF-SCORE-001",
        target_name="ALPHA SA",
        acquirer_name="Acquirer SE",
        announcement_date=date(2025, 1, 1),
        deal_type="opa",
        status="announced",
    )
    db_session.add(deal)
    await db_session.commit()

    model = _quick_model()
    out = await score_deal(deal.id, model, db_session)
    assert out is not None
    assert 0.0 <= out.p_completion <= 1.0
    assert 1 <= out.score_stars <= 5  # noqa: PLR2004
    assert out.decision in {"enter", "wait", "skip"}
    assert len(out.top_3_positive_factors) <= 3  # noqa: PLR2004
    assert len(out.top_3_risk_factors) <= 3  # noqa: PLR2004
    assert out.model_version == "quick"


@pytest.mark.integration
async def test_score_deal_returns_none_for_missing_id(db_session) -> None:  # type: ignore[no-untyped-def]
    model = _quick_model()
    out = await score_deal(999_999, model, db_session)
    assert out is None
