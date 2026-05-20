"""Phase 6 V1 validation — TimeSeriesSplit cross-validation.

Splits by `earliest_announcement` of each labelled cluster: training
folds contain rows announced strictly before the validation fold's
earliest announcement minus `gap_days`. This prevents leakage from
look-ahead labels that the operator filled using post-announcement
news.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score


@dataclass(frozen=True, slots=True)
class FoldResult:
    fold: int
    train_n: int
    valid_n: int
    valid_label_pos: int
    valid_label_neg: int
    auc: float | None
    brier: float | None
    train_min_date: str
    train_max_date: str
    valid_min_date: str
    valid_max_date: str


@dataclass
class ValidationReport:
    folds: list[FoldResult]
    overall_auc: float | None
    overall_brier: float | None
    calibration_curve: list[tuple[float, float, int]]
    feature_top_positives: list[tuple[str, float]]
    feature_top_negatives: list[tuple[str, float]]
    notes: list[str]

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append("# Phase 6 V1 — Validation report\n")
        lines.append("## Cross-validation (date-ordered, gap=90 j)\n")
        header = (
            "| Fold | Train n | Valid n | Valid pos/neg | AUC | Brier | "
            "Train range | Valid range |\n"
        )
        lines.append(header)
        lines.append("|---|---:|---:|---|---:|---:|---|---|\n")
        for fr in self.folds:
            auc = "n/a" if fr.auc is None else f"{fr.auc:.3f}"
            br = "n/a" if fr.brier is None else f"{fr.brier:.3f}"
            lines.append(
                f"| {fr.fold} | {fr.train_n} | {fr.valid_n} | "
                f"{fr.valid_label_pos}/{fr.valid_label_neg} | "
                f"{auc} | {br} | "
                f"{fr.train_min_date} → {fr.train_max_date} | "
                f"{fr.valid_min_date} → {fr.valid_max_date} |\n"
            )
        overall_auc = "n/a" if self.overall_auc is None else f"{self.overall_auc:.3f}"
        overall_brier = "n/a" if self.overall_brier is None else f"{self.overall_brier:.3f}"
        lines.append(f"\n**Overall pooled AUC:** {overall_auc}\n")
        lines.append(f"**Overall pooled Brier:** {overall_brier}\n")
        lines.append("\n## Calibration deciles (in-sample on full training set)\n")
        lines.append("| Predicted-prob bin (mid) | Empirical rate | n |\n")
        lines.append("|---:|---:|---:|\n")
        for mid, rate, n in self.calibration_curve:
            lines.append(f"| {mid:.2f} | {rate:.3f} | {n} |\n")
        lines.append("\n## Top positive contributors (full-data refit)\n")
        for name, val in self.feature_top_positives:
            lines.append(f"- `{name}` → {val:+.3f}\n")
        lines.append("\n## Top negative contributors (full-data refit)\n")
        for name, val in self.feature_top_negatives:
            lines.append(f"- `{name}` → {val:+.3f}\n")
        lines.append("\n## Notes\n")
        for n in self.notes:
            lines.append(f"- {n}\n")
        return "".join(lines)


def chronological_folds(
    dates: list[Any],
    n_splits: int = 3,
    gap_days: int = 90,
) -> list[tuple[list[int], list[int]]]:
    """Return n_splits (train_idx, valid_idx) pairs. Each validation fold
    is a chronological chunk; training data is everything announced more
    than `gap_days` BEFORE the earliest valid-fold date."""
    n = len(dates)
    order = np.argsort(dates)
    folds: list[tuple[list[int], list[int]]] = []
    chunk_size = max(n // (n_splits + 1), 1)
    for s in range(n_splits):
        valid_start = (s + 1) * chunk_size
        valid_end = (s + 2) * chunk_size if s < n_splits - 1 else n
        valid_idx_ordered = order[valid_start:valid_end].tolist()
        if not valid_idx_ordered:
            continue
        valid_min_date = min(dates[i] for i in valid_idx_ordered)
        train_idx = [
            int(i)
            for i in order[:valid_start]
            if dates[i] <= valid_min_date - timedelta(days=gap_days)
        ]
        if train_idx and valid_idx_ordered:
            folds.append((train_idx, [int(i) for i in valid_idx_ordered]))
    return folds


def evaluate(
    model_class: Any,
    X: pd.DataFrame,
    y: np.ndarray,
    dates: list[Any],
    *,
    n_splits: int = 3,
    gap_days: int = 90,
) -> ValidationReport:
    folds = chronological_folds(dates, n_splits=n_splits, gap_days=gap_days)
    fold_results: list[FoldResult] = []
    all_y: list[int] = []
    all_p: list[float] = []
    notes: list[str] = []

    for fi, (train_idx, valid_idx) in enumerate(folds):
        y_train = y[train_idx]
        # Cannot fit if a fold has only one class.
        if len(np.unique(y_train)) < 2:  # noqa: PLR2004
            notes.append(f"Fold {fi}: train fold has a single class — skipped.")
            continue
        model = model_class()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(X.iloc[train_idx], y_train)
        proba = model.predict_proba(X.iloc[valid_idx])[:, 1]
        y_valid = y[valid_idx]
        auc = None
        if len(np.unique(y_valid)) >= 2:  # noqa: PLR2004
            auc = float(roc_auc_score(y_valid, proba))
        brier = float(brier_score_loss(y_valid, proba))
        fold_results.append(
            FoldResult(
                fold=fi,
                train_n=len(train_idx),
                valid_n=len(valid_idx),
                valid_label_pos=int((y_valid == 1).sum()),
                valid_label_neg=int((y_valid == 0).sum()),
                auc=auc,
                brier=brier,
                train_min_date=str(min(dates[i] for i in train_idx)),
                train_max_date=str(max(dates[i] for i in train_idx)),
                valid_min_date=str(min(dates[i] for i in valid_idx)),
                valid_max_date=str(max(dates[i] for i in valid_idx)),
            )
        )
        all_y.extend(y_valid.tolist())
        all_p.extend(proba.tolist())

    overall_auc = None
    overall_brier = None
    if all_y and len(set(all_y)) >= 2:  # noqa: PLR2004
        overall_auc = float(roc_auc_score(all_y, all_p))
    if all_y:
        overall_brier = float(brier_score_loss(all_y, all_p))

    # In-sample calibration on full training set (5 deciles to stay
    # readable with tiny N).
    final_model = model_class()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        final_model.fit(X, y)
    p_in = final_model.predict_proba(X)[:, 1]
    bins = np.linspace(0, 1, 6)
    calibration_curve: list[tuple[float, float, int]] = []
    for i in range(len(bins) - 1):
        lo, hi = bins[i], bins[i + 1]
        mask = (p_in >= lo) & (p_in < hi if i < len(bins) - 2 else p_in <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        emp = float(y[mask].mean())
        calibration_curve.append(((lo + hi) / 2, emp, n))

    # Feature contributions (coefficients from the inner refit).
    pos_contrib: list[tuple[str, float]] = []
    neg_contrib: list[tuple[str, float]] = []
    if (
        hasattr(final_model, "inner_clf")
        and final_model.inner_clf is not None
        and hasattr(final_model, "feature_names_post_transform")
    ):
        coefs = final_model.inner_clf.coef_[0]
        named = list(zip(final_model.feature_names_post_transform, coefs, strict=True))
        named.sort(key=lambda kv: kv[1])
        neg_contrib = [(n, float(v)) for n, v in named[:5]]
        pos_contrib = [(n, float(v)) for n, v in named[-5:][::-1]]

    return ValidationReport(
        folds=fold_results,
        overall_auc=overall_auc,
        overall_brier=overall_brier,
        calibration_curve=calibration_curve,
        feature_top_positives=pos_contrib,
        feature_top_negatives=neg_contrib,
        notes=notes,
    )


def write_report_md(report: ValidationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.to_markdown(), encoding="utf-8")
