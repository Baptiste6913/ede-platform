"""Phase 6 V1 scoring model.

Pipeline:
    [Numeric  ] IterativeImputer  → StandardScaler
    [Boolean  ] (passthrough — already 0/1)
    [Categorical] OneHotEncoder(handle_unknown='ignore')
                  →
                  LogisticRegression(
                      penalty='elasticnet', solver='saga',
                      l1_ratio=0.5, C=1.0, class_weight='balanced',
                      max_iter=2000,
                  )
                  →
                  CalibratedClassifierCV(method='isotonic', cv=3)

The calibrator wraps the whole sklearn `Pipeline` (not just the
LogisticRegression) so cross-validated probabilities account for the
imputer + scaler. Coefficients for the explainability `top_3_*_factors`
in `inference.py` are read from the inner LogReg fitted on the FULL
training set as a separate refit step.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.experimental import enable_iterative_imputer  # noqa: F401 — side-effect import
from sklearn.impute import IterativeImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.scoring.features import (
    BOOLEAN_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
)


def _build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("impute", IterativeImputer(random_state=42, max_iter=20)),
                        ("scale", StandardScaler()),
                    ]
                ),
                list(NUMERIC_FEATURES),
            ),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                list(CATEGORICAL_FEATURES),
            ),
            (
                "bool",
                "passthrough",
                list(BOOLEAN_FEATURES),
            ),
        ],
        remainder="drop",
    )


def _build_estimator() -> Pipeline:
    pre = _build_preprocessor()
    clf = LogisticRegression(
        penalty="elasticnet",
        solver="saga",
        l1_ratio=0.5,
        C=1.0,
        class_weight="balanced",
        max_iter=2000,
        random_state=42,
    )
    return Pipeline(steps=[("pre", pre), ("clf", clf)])


@dataclass
class ScoringModel:
    """Wrapper around the trained calibrated estimator + a refit `inner_clf`
    used purely for coefficient-based explanations."""

    calibrated: CalibratedClassifierCV | None = None
    inner_clf: LogisticRegression | None = None
    pre: ColumnTransformer | None = None
    feature_names_post_transform: list[str] = field(default_factory=list)
    trained_at_utc: str = ""
    n_samples_train: int = 0
    class_balance: dict[str, int] = field(default_factory=dict)
    version: str = "scoring_v1"

    def fit(self, X: pd.DataFrame, y: np.ndarray | pd.Series) -> ScoringModel:
        """Train both:
        1. the calibrated wrapper (for probability output), and
        2. a refit inner pipeline (for coefficients, since CalibratedCV
           internally retrains on folds and doesn't expose stable coefs).
        """
        # The calibrator
        base = _build_estimator()
        self.calibrated = CalibratedClassifierCV(base, method="isotonic", cv=3)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            warnings.simplefilter("ignore", FutureWarning)
            self.calibrated.fit(X, y)

        # The full-data refit for explanations
        inner_pipeline = _build_estimator()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            warnings.simplefilter("ignore", FutureWarning)
            inner_pipeline.fit(X, y)
        self.pre = inner_pipeline.named_steps["pre"]
        self.inner_clf = inner_pipeline.named_steps["clf"]

        # Pull post-transform feature names directly from the fitted
        # ColumnTransformer — handles IterativeImputer dropping entirely-
        # NaN columns transparently.
        try:
            raw_names = list(self.pre.get_feature_names_out())
        except Exception:
            raw_names = [f"feat_{i}" for i in range(self.inner_clf.coef_.shape[1])]
        # Strip the ColumnTransformer prefix ('num__', 'cat__', 'bool__').
        self.feature_names_post_transform = [
            n.split("__", 1)[1] if "__" in n else n for n in raw_names
        ]

        self.trained_at_utc = datetime.now(tz=UTC).isoformat()
        self.n_samples_train = int(len(y))
        y_arr = np.asarray(y)
        self.class_balance = {
            "n_label_0": int((y_arr == 0).sum()),
            "n_label_1": int((y_arr == 1).sum()),
        }
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.calibrated is None:
            raise RuntimeError("Model not trained; call fit() first")
        return self.calibrated.predict_proba(X)

    def feature_contributions(self, row: pd.DataFrame) -> list[tuple[str, float]]:
        """Per-feature coefficient x scaled value. Higher = more positive
        (label=1 nudging). Lower = more negative."""
        if self.inner_clf is None or self.pre is None:
            raise RuntimeError("Model not trained; call fit() first")
        Xt = self.pre.transform(row)
        coefs = self.inner_clf.coef_[0]
        contributions = (np.asarray(Xt).flatten() * coefs).tolist()
        return list(zip(self.feature_names_post_transform, contributions, strict=True))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> ScoringModel:
        obj = joblib.load(path)
        if not isinstance(obj, ScoringModel):
            raise TypeError(f"Loaded object is not a ScoringModel: {type(obj)}")
        return obj


def map_p_to_stars(p: float) -> int:
    """Brief mapping: p<0.3→1, p<0.5→2, p<0.7→3, p<0.85→4, p≥0.85→5."""
    if p < 0.3:  # noqa: PLR2004
        return 1
    if p < 0.5:  # noqa: PLR2004
        return 2
    if p < 0.7:  # noqa: PLR2004
        return 3
    if p < 0.85:  # noqa: PLR2004
        return 4
    return 5


def map_p_to_decision(p: float) -> str:
    if p >= 0.7:  # noqa: PLR2004
        return "enter"
    if p >= 0.5:  # noqa: PLR2004
        return "wait"
    return "skip"


def clusters_to_dataframe(clusters: list[Any]) -> tuple[pd.DataFrame, np.ndarray, list[int]]:
    """Returns (X, y_labelled_subset, indices_of_labelled).

    `X` contains every cluster; `y` and `indices` are restricted to
    rows with a non-NULL `.label`. The caller trains on X.iloc[indices]
    and predicts on the full X.
    """
    rows: list[dict[str, Any]] = []
    labels: list[int] = []
    labelled_idx: list[int] = []
    for i, cf in enumerate(clusters):
        from src.scoring.features import features_to_vector

        rows.append(features_to_vector(cf.features))
        if cf.label is not None:
            labels.append(int(cf.label))
            labelled_idx.append(i)
    X = pd.DataFrame(rows)
    return X, np.array(labels), labelled_idx
