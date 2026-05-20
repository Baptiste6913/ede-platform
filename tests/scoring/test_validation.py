"""Unit tests for src.scoring.validation — fold split + report shape."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.scoring.model import ScoringModel
from src.scoring.validation import chronological_folds, evaluate, write_report_md


def test_chronological_folds_respects_gap() -> None:
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(20)]
    folds = chronological_folds(dates, n_splits=3, gap_days=5)
    for train_idx, valid_idx in folds:
        if not train_idx or not valid_idx:
            continue
        max_train_date = max(dates[i] for i in train_idx)
        min_valid_date = min(dates[i] for i in valid_idx)
        assert (min_valid_date - max_train_date).days >= 5  # noqa: PLR2004 — gap respected


def test_chronological_folds_skips_empty_validation_windows() -> None:
    # With only 3 points and 3 splits, validation windows are size 0
    # in the middle splits — must be filtered out cleanly.
    dates = [date(2024, 1, 1), date(2024, 6, 1), date(2025, 1, 1)]
    folds = chronological_folds(dates, n_splits=3, gap_days=0)
    for _, valid_idx in folds:
        assert len(valid_idx) >= 1


def test_evaluate_report_has_folds_and_calibration() -> None:
    # CalibratedClassifierCV(cv=3) needs ≥3 examples per class — bump n_neg
    # high enough that each fold's training subset retains the minimum.
    rng = np.random.default_rng(seed=0)
    n_pos = 40
    n_neg = 30
    n_total = n_pos + n_neg
    # Interleave labels along the time axis so every chronological fold
    # has both classes available for training/validation.
    indices = list(range(n_total))
    rng.shuffle(indices)
    labels = np.zeros(n_total, dtype=int)
    labels[indices[:n_pos]] = 1
    X = pd.DataFrame(
        {
            "bid_premium_pct": rng.normal(20, 5, n_total),
            "relative_size": rng.normal(1, 0.3, n_total),
            "min_acceptance_threshold": rng.normal(0.6, 0.05, n_total),
            "days_to_expected_close": rng.normal(60, 10, n_total),
            "events_count": rng.integers(1, 6, n_total).astype(float),
            "deal_type": ["opa"] * n_total,
            "payment_type": ["cash"] * n_total,
            "jurisdiction": ["FR"] * n_total,
            "target_sector": ["unknown"] * n_total,
            "acquirer_type": ["corporate" if labels[i] == 1 else "family" for i in range(n_total)],
            "cross_border": [0.0] * n_total,
            "has_irrevocable_undertaking": [0.0] * n_total,
            "fdi_risk_flag": [0.0] * n_total,
        }
    )
    y = labels
    dates = [date(2024, 1, 1) + timedelta(days=i * 7) for i in range(n_total)]

    report = evaluate(
        lambda: ScoringModel(version="cv"),
        X,
        y,
        dates,
        n_splits=2,
        gap_days=14,
    )
    # At least one fold completed
    assert len(report.folds) >= 1
    # Calibration deciles non-empty
    assert len(report.calibration_curve) >= 1
    # MD render produces a non-empty string
    md = report.to_markdown()
    assert "Validation report" in md


def test_write_report_md_creates_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from src.scoring.validation import FoldResult, ValidationReport

    report = ValidationReport(
        folds=[
            FoldResult(
                fold=0, train_n=10, valid_n=4, valid_label_pos=3, valid_label_neg=1,
                auc=0.8, brier=0.12, train_min_date="2024-01-01",
                train_max_date="2024-06-01", valid_min_date="2024-09-01",
                valid_max_date="2024-12-01",
            )
        ],
        overall_auc=0.8,
        overall_brier=0.12,
        calibration_curve=[(0.5, 0.5, 4)],
        feature_top_positives=[("events_count", 1.2)],
        feature_top_negatives=[("deal_type_opa_simplifiee", -1.1)],
        notes=["sample only"],
    )
    path = tmp_path / "validation_report.md"
    write_report_md(report, path)
    text = path.read_text(encoding="utf-8")
    assert "Validation report" in text
    assert "events_count" in text
