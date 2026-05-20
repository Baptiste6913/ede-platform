"""Scoring engine V1 — Phase 6.

Logistic-regression (ElasticNet) + IsotonicCalibration over 12 features
extracted from the existing `deals` rows. Trained on the operator-
labelled subset (~131 cluster rows = ~222 underlying deal rows).

Public surface:
- `extract_cluster_features(target, jurisdiction, session)` — features
  aggregated at the cluster level (handles FR multi-stage chains).
- `ScoringModel` — fit/predict/save wrapper around the sklearn Pipeline.
- `score_deal(deal_id, model)` — async inference for one deal_id, returns
  the full V1 payload (p_completion, score_stars, top factors).
"""

from src.scoring.features import (
    FEATURE_NAMES,
    NUMERIC_FEATURES,
    extract_cluster_features,
)
from src.scoring.inference import score_deal
from src.scoring.model import ScoringModel

__all__ = [
    "FEATURE_NAMES",
    "NUMERIC_FEATURES",
    "ScoringModel",
    "extract_cluster_features",
    "score_deal",
]
