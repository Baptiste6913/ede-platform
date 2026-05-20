"""Unit tests for src.scoring.model — Pipeline shape, mapping helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.scoring.model import (
    ScoringModel,
    map_p_to_decision,
    map_p_to_stars,
)


@pytest.mark.parametrize(
    ("p", "expected"),
    [
        (0.0, 1),
        (0.29, 1),
        (0.3, 2),
        (0.49, 2),
        (0.5, 3),
        (0.69, 3),
        (0.7, 4),
        (0.84, 4),
        (0.85, 5),
        (1.0, 5),
    ],
)
def test_map_p_to_stars(p: float, expected: int) -> None:
    assert map_p_to_stars(p) == expected


@pytest.mark.parametrize(
    ("p", "expected"),
    [(0.0, "skip"), (0.49, "skip"), (0.5, "wait"), (0.69, "wait"), (0.7, "enter"), (1.0, "enter")],
)
def test_map_p_to_decision(p: float, expected: str) -> None:
    assert map_p_to_decision(p) == expected


def _synthetic_training_data(n_pos: int = 30, n_neg: int = 8) -> tuple[pd.DataFrame, np.ndarray]:
    """Build a tiny, well-separated dataset so the LogReg can train
    deterministically without numpy/sklearn warnings on edge folds."""
    rng = np.random.default_rng(seed=42)

    pos = pd.DataFrame(
        {
            "bid_premium_pct": rng.normal(30, 5, n_pos),
            "relative_size": rng.normal(1.5, 0.3, n_pos),
            "min_acceptance_threshold": rng.normal(0.7, 0.05, n_pos),
            "days_to_expected_close": rng.normal(60, 10, n_pos),
            "events_count": rng.integers(3, 8, n_pos).astype(float),
            "deal_type": ["opa"] * n_pos,
            "payment_type": ["cash"] * n_pos,
            "jurisdiction": ["FR"] * n_pos,
            "target_sector": ["unknown"] * n_pos,
            "acquirer_type": ["corporate"] * n_pos,
            "cross_border": [0.0] * n_pos,
            "has_irrevocable_undertaking": [1.0] * n_pos,
            "fdi_risk_flag": [0.0] * n_pos,
        }
    )
    neg = pd.DataFrame(
        {
            "bid_premium_pct": rng.normal(5, 3, n_neg),
            "relative_size": rng.normal(0.4, 0.1, n_neg),
            "min_acceptance_threshold": rng.normal(0.5, 0.05, n_neg),
            "days_to_expected_close": rng.normal(200, 30, n_neg),
            "events_count": [1.0] * n_neg,
            "deal_type": ["opa_simplifiee"] * n_neg,
            "payment_type": ["stock"] * n_neg,
            "jurisdiction": ["FR"] * n_neg,
            "target_sector": ["unknown"] * n_neg,
            "acquirer_type": ["family"] * n_neg,
            "cross_border": [0.0] * n_neg,
            "has_irrevocable_undertaking": [0.0] * n_neg,
            "fdi_risk_flag": [1.0] * n_neg,
        }
    )
    X = pd.concat([pos, neg], ignore_index=True)
    y = np.array([1] * n_pos + [0] * n_neg)
    return X, y


def test_scoring_model_fits_and_predicts_proba_in_range() -> None:
    X, y = _synthetic_training_data()
    model = ScoringModel(version="test_v1")
    model.fit(X, y)
    proba = model.predict_proba(X)
    assert proba.shape == (len(X), 2)
    assert np.all(proba >= 0.0) and np.all(proba <= 1.0)
    assert model.n_samples_train == len(X)
    assert model.class_balance == {"n_label_0": 8, "n_label_1": 30}


def test_scoring_model_learns_class_separation() -> None:
    """On well-separated synthetic data the mean positive-class proba
    on label=1 examples should be clearly higher than on label=0."""
    X, y = _synthetic_training_data()
    model = ScoringModel(version="test_v1")
    model.fit(X, y)
    proba = model.predict_proba(X)[:, 1]
    mean_pos = float(np.mean(proba[y == 1]))
    mean_neg = float(np.mean(proba[y == 0]))
    assert mean_pos - mean_neg > 0.2


def test_scoring_model_feature_contributions_align_with_post_transform_names() -> None:
    X, y = _synthetic_training_data()
    model = ScoringModel(version="test_v1")
    model.fit(X, y)
    contributions = model.feature_contributions(X.head(1))
    # Same count as inner_clf.coef_[0]
    assert len(contributions) == model.inner_clf.coef_.shape[1]
    # Each contribution is (name, float)
    for name, val in contributions:
        assert isinstance(name, str)
        assert isinstance(val, float)


def test_scoring_model_save_and_load_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    X, y = _synthetic_training_data()
    model = ScoringModel(version="test_v1")
    model.fit(X, y)
    p_path = tmp_path / "model.pkl"
    model.save(p_path)

    loaded = ScoringModel.load(p_path)
    assert loaded.version == "test_v1"
    assert loaded.n_samples_train == len(X)
    np.testing.assert_array_almost_equal(loaded.predict_proba(X), model.predict_proba(X), decimal=4)


def test_scoring_model_load_rejects_wrong_type(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import joblib

    p = tmp_path / "wrong.pkl"
    joblib.dump({"not": "a-model"}, p)
    with pytest.raises(TypeError):
        ScoringModel.load(p)
