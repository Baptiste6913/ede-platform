"""Phase 6 Step-9 — train + score every cluster, persist + audit.

Pipeline:
  1. Pull every cluster (target+jurisdiction) from the live DB.
  2. Build the feature matrix; restrict the training subset to clusters
     with a non-NULL `completion_label`.
  3. Train `ScoringModel`, persist to `models/scoring_v1_{ts}.pkl`.
  4. Run cross-validation, write `artifacts/phase-06/validation_report.md`.
  5. Score every cluster, persist to `scores` table + flush
     `artifacts/phase-06/scoring_run_{ts}.json`.
  6. Sanity-check 5 named deals + Discord stub (Phase 11 wiring).

Usage:
    DATABASE_URL=... python scripts/score_deals_run.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.db import get_engine
from src.core.logging import configure_logging
from src.core.models import Score
from src.scoring.features import iter_all_clusters
from src.scoring.inference import score_deal
from src.scoring.model import (
    ScoringModel,
    clusters_to_dataframe,
)
from src.scoring.validation import evaluate, write_report_md

_log = structlog.get_logger("scoring.run")

SANITY_TARGETS: list[tuple[str, str, str, str]] = [
    # (jurisdiction, target_name_substring, expectation, why)
    ("DE", "MorphoSys", "HIGH", "Novartis delisting closed Q2 2024"),
    ("IT", "Banco BPM", "LOW", "UniCredit withdrew Banco BPM offer July 2025"),
    ("DE", "Covestro", "HIGH", "ADNOC FSR cleared Nov 2025, acceptance 91%"),
    ("IT", "Mediobanca", "HIGH", "MPS OPAS closed Sept 2025, 86% adesione"),
    ("DE", "1&1", "HIGH", "United Internet partial 85% July 2025"),
]


def _jsonable(value: Any) -> Any:
    """Postgres JSONB rejects NaN/Infinity. Convert them to None
    recursively while leaving everything else untouched."""
    import math

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


async def _persist_score(
    session_factory: async_sessionmaker,
    out: Any,
    features_snapshot: dict[str, Any],
) -> None:
    async with session_factory() as session:
        session.add(
            Score(
                deal_id=out.deal_id,
                p_completion=Decimal(str(out.p_completion)),
                decision=out.decision,
                model_version=out.model_version,
                features=_jsonable(features_snapshot),
                score_stars=out.score_stars,
                risk_factors=_jsonable(out.top_3_risk_factors),
                positive_factors=_jsonable(out.top_3_positive_factors),
            )
        )
        await session.commit()


async def main() -> int:
    configure_logging(level="INFO")
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    artifacts = Path("artifacts/phase-06")
    artifacts.mkdir(parents=True, exist_ok=True)
    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)

    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with sf() as session:
        clusters = await iter_all_clusters(session)
    _log.info("scoring.clusters_loaded", n=len(clusters))

    X, y, labelled_idx = clusters_to_dataframe(clusters)
    _log.info(
        "scoring.training_set",
        labelled=len(labelled_idx),
        unlabelled=len(clusters) - len(labelled_idx),
    )

    if len(labelled_idx) < 20:  # noqa: PLR2004
        _log.error("scoring.too_few_labels", n=len(labelled_idx))
        return 2

    X_train = X.iloc[labelled_idx].reset_index(drop=True)
    train_dates = [clusters[i].earliest_announcement for i in labelled_idx]

    model = ScoringModel(version=f"scoring_v1_{ts}")
    model.fit(X_train, y)
    model_path = models_dir / f"scoring_v1_{ts}.pkl"
    model.save(model_path)
    _log.info("scoring.model_trained", path=str(model_path), train_n=len(y))

    # Cross-validation
    report = evaluate(
        lambda: ScoringModel(version="cv_fold"),
        X_train,
        y,
        train_dates,
        n_splits=3,
        gap_days=90,
    )
    report_path = artifacts / "validation_report.md"
    write_report_md(report, report_path)
    _log.info(
        "scoring.validation",
        overall_auc=report.overall_auc,
        overall_brier=report.overall_brier,
    )

    # Inference on every cluster
    scoring_summary: list[dict[str, Any]] = []
    async with sf() as session:
        for cf in clusters:
            out = await score_deal(cf.representative_deal_id, model, session)
            if out is None:
                continue
            await _persist_score(sf, out, cf.features)
            scoring_summary.append(
                {
                    "deal_id": out.deal_id,
                    "target": out.target_name,
                    "jurisdiction": out.jurisdiction,
                    "p_completion": out.p_completion,
                    "stars": out.score_stars,
                    "decision": out.decision,
                    "label": cf.label,
                }
            )

    distribution: dict[str, int] = {f"{s}_stars": 0 for s in range(1, 6)}
    for r in scoring_summary:
        distribution[f"{r['stars']}_stars"] += 1

    top_10_high = sorted(scoring_summary, key=lambda r: -r["p_completion"])[:10]
    top_10_low = sorted(scoring_summary, key=lambda r: r["p_completion"])[:10]

    sanity: list[dict[str, Any]] = []
    for jur, sub, expected, why in SANITY_TARGETS:
        match = next(
            (
                r
                for r in scoring_summary
                if r["jurisdiction"] == jur and sub.lower() in r["target"].lower()
            ),
            None,
        )
        sanity.append(
            {
                "jurisdiction": jur,
                "target_substring": sub,
                "expectation": expected,
                "why": why,
                "matched_target": match["target"] if match else None,
                "p_completion": match["p_completion"] if match else None,
                "stars": match["stars"] if match else None,
                "label_y_in_db": match["label"] if match else None,
            }
        )

    payload: dict[str, Any] = {
        "phase": "phase-06-scoring-v1-run",
        "executed_at_utc": ts,
        "model_path": str(model_path),
        "model_version": model.version,
        "n_clusters_scored": len(scoring_summary),
        "n_clusters_labelled_for_training": len(labelled_idx),
        "class_balance": model.class_balance,
        "validation": {
            "overall_auc": report.overall_auc,
            "overall_brier": report.overall_brier,
            "n_folds": len(report.folds),
        },
        "distribution": distribution,
        "top_10_high_p_completion": top_10_high,
        "top_10_low_p_completion": top_10_low,
        "sanity_check_5_deals": sanity,
    }
    out_path = artifacts / f"scoring_run_{ts}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Permanent latest copy too
    (artifacts / "scoring_run_latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
