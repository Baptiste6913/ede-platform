"""Phase 6 V1 inference — `score_deal(deal_id, model)` async helper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from src.scoring.features import (
    extract_cluster_features,
    features_to_vector,
)
from src.scoring.model import map_p_to_decision, map_p_to_stars

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.scoring.model import ScoringModel


@dataclass(frozen=True, slots=True)
class ScoreOutput:
    deal_id: int
    target_name: str
    jurisdiction: str
    p_completion: float
    score_stars: int
    decision: str
    top_3_positive_factors: list[dict[str, Any]] = field(default_factory=list)
    top_3_risk_factors: list[dict[str, Any]] = field(default_factory=list)
    model_version: str = ""
    scored_at: str = ""


async def score_deal(
    deal_id: int,
    model: ScoringModel,
    session: AsyncSession,
) -> ScoreOutput | None:
    """Score one deal by deal_id. Aggregates the cluster (target+jur)
    so multi-stage FR filings share one prediction."""
    from sqlalchemy import select

    from src.core.models import Deal

    deal = await session.get(Deal, deal_id)
    if deal is None:
        return None
    cf = await extract_cluster_features(deal.target_name, deal.juridiction, session)
    if cf is None:
        return None

    row = pd.DataFrame([features_to_vector(cf.features)])
    p = float(model.predict_proba(row)[0, 1])
    stars = map_p_to_stars(p)
    decision = map_p_to_decision(p)
    contributions = model.feature_contributions(row)
    sorted_contributions = sorted(contributions, key=lambda kv: kv[1])
    top_neg = [{"feature": n, "contribution": round(v, 4)} for n, v in sorted_contributions[:3]]
    top_pos = [
        {"feature": n, "contribution": round(v, 4)} for n, v in sorted_contributions[-3:][::-1]
    ]
    _ = select  # keep import in case of future enriched queries

    return ScoreOutput(
        deal_id=cf.representative_deal_id,
        target_name=cf.target_name,
        jurisdiction=cf.jurisdiction,
        p_completion=round(p, 4),
        score_stars=stars,
        decision=decision,
        top_3_positive_factors=top_pos,
        top_3_risk_factors=top_neg,
        model_version=model.version,
        scored_at=datetime.now(tz=UTC).isoformat(),
    )
