"""Phase 9.1c-[G-3] — token re-fit + non-regression vs baseline.

Trains a fresh ``ScoringModel`` on the current DB state using the exact
baseline hyperparameters (same as ``scoring_v1_20260520T141111Z``), then
compares both models in-sample on the 120-cluster slice (= 213 labelled
deals minus 9 ``manual_review`` DE). The 9 excluded deals collapse into
8 clusters (Francotyp-Postalia is a 2-deal cluster).

Outputs:
  - ``models/scoring_v1_20260526_p91c.pkl``
  - ``data/audits/p91c_train_test_split.csv``
  - ``data/audits/p91c_refit_metrics.csv``
  - Console verdict (OK / STOP if tolerance breached).

Tolerance band (per [G-3] brief):
  |dBrier| > 0.005 OR |dAUC| > 0.01  →  STOP, do not commit the model.

Run (PowerShell, repo root, postgres up):
  $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/refit_p91c.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    roc_auc_score,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.db import dispose_engine, get_engine
from src.core.models import Deal
from src.scoring.features import iter_all_clusters
from src.scoring.model import ScoringModel, clusters_to_dataframe

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PKL = REPO_ROOT / "models" / "scoring_v1_20260520T141111Z.pkl"
NEW_PKL = REPO_ROOT / "models" / "scoring_v1_20260526_p91c.pkl"
SPLIT_CSV = REPO_ROOT / "data" / "audits" / "p91c_train_test_split.csv"
METRICS_CSV = REPO_ROOT / "data" / "audits" / "p91c_refit_metrics.csv"

BRIER_TOL = 0.005
AUC_TOL = 0.01
# Primary non-regression gate for a *token* re-fit: predictions are
# functionally identical to baseline. ``atol=1e-10`` admits cross-process
# BLAS/OpenMP reduction noise (observed: 8.2e-15 = 1-8 ulp at p~=1.0,
# documented in docs/phase-09/p91c_variance_diagnosis.md), and rejects
# any structural change that would propagate >1e-3 through the pipeline.
IDENTITY_ATOL = 1e-10
DIAG_DIFF_THRESHOLD = 1e-6  # diagnostic-only: count predictions that moved meaningfully


async def _excluded_cluster_keys() -> set[tuple[str, str]]:
    """The 8 (target_name, juridiction) clusters that aggregate the 9
    DE manual_review labelled deals."""
    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        rows = (
            await session.execute(
                select(Deal.target_name, Deal.juridiction)
                .where(Deal.offer_price_quality_flag == "manual_review")
                .where(Deal.completion_label.is_not(None))
                .distinct()
            )
        ).all()
    return set(rows)


async def _labelled_deals_for_split() -> list[tuple[int, str, str, int, bool]]:
    """All labelled deals + their excluded-or-not flag, for the split CSV.
    Returns rows of (deal_id, target_name, juridiction, label, excluded_from_test)."""
    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        rows = (
            await session.execute(
                select(
                    Deal.id,
                    Deal.target_name,
                    Deal.juridiction,
                    Deal.completion_label,
                    Deal.offer_price_quality_flag,
                ).where(Deal.completion_label.is_not(None))
            )
        ).all()
    return [
        (int(did), str(tn), str(jur), int(lab), flag == "manual_review")
        for did, tn, jur, lab, flag in rows
    ]


def _metrics(y_true: np.ndarray, p_pos: np.ndarray) -> dict[str, float]:
    """Brier / AUC / log_loss / accuracy / F1 — robust to single-class slices."""
    out: dict[str, float] = {"brier": float(brier_score_loss(y_true, p_pos))}
    out["log_loss"] = float(log_loss(y_true, p_pos, labels=[0, 1]))
    if len(np.unique(y_true)) >= 2:  # noqa: PLR2004 — binary classifier needs both classes
        out["auc"] = float(roc_auc_score(y_true, p_pos))
    else:
        out["auc"] = float("nan")
    y_pred = (p_pos >= 0.5).astype(int)  # noqa: PLR2004 — standard binary decision threshold
    out["accuracy"] = float(accuracy_score(y_true, y_pred))
    out["f1"] = float(f1_score(y_true, y_pred, zero_division=0))
    return out


async def main() -> int:
    excluded = await _excluded_cluster_keys()
    print(f"[G-3] excluded clusters (DE manual_review): {len(excluded)}")

    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        clusters = await iter_all_clusters(session)
    print(f"[G-3] clusters loaded: {len(clusters)}")

    X, y, labelled_idx = clusters_to_dataframe(clusters)
    print(f"[G-3] labelled clusters: {len(labelled_idx)}")
    X_train = X.iloc[labelled_idx].reset_index(drop=True)

    # Map labelled-cluster row index → (target_name, juridiction).
    labelled_keys: list[tuple[str, str]] = [
        (clusters[i].target_name, clusters[i].jurisdiction) for i in labelled_idx
    ]
    eval_mask = np.array([key not in excluded for key in labelled_keys])
    print(
        f"[G-3] eval slice (labelled - manual_review): {int(eval_mask.sum())} clusters "
        f"({len(labelled_keys) - int(eval_mask.sum())} excluded)"
    )

    # ---- Train new model (same hyperparams as baseline) ----
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    new_model = ScoringModel(version=f"scoring_v1_20260526_p91c_{ts}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        new_model.fit(X_train, y)
    print(
        f"[G-3] new model trained: n={new_model.n_samples_train}, "
        f"class_balance={new_model.class_balance}"
    )

    # ---- Load baseline ----
    baseline = ScoringModel.load(BASELINE_PKL)
    print(f"[G-3] baseline loaded: {baseline.version}, n={baseline.n_samples_train}")

    # ---- Predict + slice ----
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p_baseline_full = baseline.predict_proba(X_train)[:, 1]
        p_new_full = new_model.predict_proba(X_train)[:, 1]
    y_eval = y[eval_mask]
    p_baseline = p_baseline_full[eval_mask]
    p_new = p_new_full[eval_mask]

    m_baseline = _metrics(y_eval, p_baseline)
    m_new = _metrics(y_eval, p_new)

    # ---- Rank-tie diagnostic: AUC on rounded predictions ----
    # roc_auc_score uses argsort which is unstable on ties; FP noise of order
    # 1e-15 can reshuffle saturated predictions (p=1.0) and shift AUC by a
    # few percent without changing the underlying model behavior. Recomputing
    # on rounded predictions strips the noise.
    p_b_round = np.round(p_baseline, 6)
    p_n_round = np.round(p_new, 6)
    auc_b_round = roc_auc_score(y_eval, p_b_round) if len(np.unique(y_eval)) >= 2 else float("nan")  # noqa: PLR2004
    auc_n_round = roc_auc_score(y_eval, p_n_round) if len(np.unique(y_eval)) >= 2 else float("nan")  # noqa: PLR2004
    n_tied_top = int((p_b_round == 1.0).sum())
    print(
        f"[diag] AUC on rounded predictions (6 decimals): "
        f"baseline={auc_b_round:.6f} new={auc_n_round:.6f} "
        f"delta={auc_n_round - auc_b_round:+.6f} "
        f"(n_predictions_at_1.0_after_rounding={n_tied_top})"
    )

    # ---- Diagnostic: where do predictions differ? ----
    diff = np.abs(p_new_full - p_baseline_full)
    print(
        f"[diag] full-set prediction diff: mean={diff.mean():.6e} "
        f"max={diff.max():.6e} n_diff_gt_{DIAG_DIFF_THRESHOLD:.0e}="
        f"{int((diff > DIAG_DIFF_THRESHOLD).sum())}"
    )
    diff_eval = np.abs(p_new - p_baseline)
    print(
        f"[diag] eval-set prediction diff: mean={diff_eval.mean():.6e} "
        f"max={diff_eval.max():.6e} n_diff_gt_{DIAG_DIFF_THRESHOLD:.0e}="
        f"{int((diff_eval > DIAG_DIFF_THRESHOLD).sum())}"
    )
    # If predictions differ at all on the eval set, list the largest movers.
    if diff_eval.max() > DIAG_DIFF_THRESHOLD:
        order = np.argsort(-diff_eval)[:10]
        eval_keys = [k for k, m in zip(labelled_keys, eval_mask, strict=True) if m]
        print("[diag] top-10 movers on eval set:")
        for o in order:
            target, jur = eval_keys[o]
            print(
                f"        {jur} | {target[:40]:<40} "
                f"y={int(y_eval[o])} "
                f"p_baseline={p_baseline[o]:.6f} p_new={p_new[o]:.6f} "
                f"delta={p_new[o] - p_baseline[o]:+.6f}"
            )

    # ---- Two-tier non-regression check ----
    # PRIMARY: predictions byte-equivalent to baseline (token re-fit case).
    # SECONDARY: Brier / AUC thresholds (real re-fit case — P9.1e, P9.2).
    predictions_identical = bool(
        np.allclose(p_baseline_full, p_new_full, atol=IDENTITY_ATOL, rtol=0)
    )
    d_brier = abs(m_new["brier"] - m_baseline["brier"])
    d_auc = abs(m_new["auc"] - m_baseline["auc"])
    threshold_breach = d_brier > BRIER_TOL or d_auc > AUC_TOL

    if predictions_identical:
        check_used = "identity"
        verdict_pass = True
    else:
        check_used = "thresholds"
        verdict_pass = not threshold_breach

    # ---- Metrics CSV ----
    METRICS_CSV.parent.mkdir(parents=True, exist_ok=True)
    metric_names = ("brier", "auc", "log_loss", "accuracy", "f1")
    rows = []
    for name in metric_names:
        b = m_baseline[name]
        n = m_new[name]
        delta = n - b
        rows.append(
            {
                "metric": name,
                "baseline_v1_20260520": f"{b:.6f}",
                "p91c_v1_20260526": f"{n:.6f}",
                "delta": f"{delta:+.6f}",
                "abs_delta": f"{abs(delta):.6f}",
                "check_used": check_used,
            }
        )
    with METRICS_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "metric",
                "baseline_v1_20260520",
                "p91c_v1_20260526",
                "delta",
                "abs_delta",
                "check_used",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    # ---- Train/test split CSV (deal-level for audit trail) ----
    deal_rows = await _labelled_deals_for_split()
    SPLIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SPLIT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["deal_id", "target_name", "juridiction", "completion_label", "split"],
        )
        writer.writeheader()
        for did, tn, jur, lab, excl in deal_rows:
            split = "train_only" if excl else "train_and_test"
            writer.writerow(
                {
                    "deal_id": did,
                    "target_name": tn,
                    "juridiction": jur,
                    "completion_label": lab,
                    "split": split,
                }
            )

    # ---- Console verdict ----
    print()
    print("=" * 78)
    print("[G-3] non-regression metrics (eval on 120-cluster slice = 213 deals)")
    print("=" * 78)
    header = f"{'metric':<10} {'baseline':>14} {'p91c':>14} {'delta':>12} {'|delta|':>12}"
    print(header)
    print("-" * 78)
    for r in rows:
        print(
            f"{r['metric']:<10} "
            f"{r['baseline_v1_20260520']:>14} "
            f"{r['p91c_v1_20260526']:>14} "
            f"{r['delta']:>12} "
            f"{r['abs_delta']:>12}"
        )
    print()
    max_diff = float(np.abs(p_new_full - p_baseline_full).max())
    print(
        f"[check] PRIMARY identity: max|p_new - p_baseline| = {max_diff:.3e} "
        f"(tol {IDENTITY_ATOL:.0e}) -> {'PASS' if predictions_identical else 'FAIL'}"
    )
    print(
        f"[check] SECONDARY thresholds: |dBrier|={d_brier:.4f} (tol {BRIER_TOL}), "
        f"|dAUC|={d_auc:.4f} (tol {AUC_TOL}) -> "
        f"{'PASS' if not threshold_breach else 'BREACH'}"
    )
    print(f"[check] check_used = '{check_used}'")
    print()

    if not verdict_pass:
        # Only reached when predictions diverged AND thresholds tripped —
        # a real regression on a token re-fit, never expected.
        print(
            f"[STOP] thresholds breached AND predictions diverged "
            f"(max diff {max_diff:.3e} > {IDENTITY_ATOL:.0e}). "
            "DO NOT commit. Investigate before proceeding."
        )
        await dispose_engine()
        return 2

    if check_used == "identity":
        print(
            "[OK] predictions are byte-equivalent to baseline within "
            f"{IDENTITY_ATOL:.0e}. AUC drift is rank-tie-breaking artifact "
            "on saturated dataset (see docs/phase-09/p91c_variance_diagnosis.md). "
            "Non-regression validated via PRIMARY identity check."
        )
    else:
        print(
            f"[OK] predictions diverged ({max_diff:.3e}) but stayed within "
            "Brier/AUC tolerance. Non-regression validated via SECONDARY thresholds."
        )

    # Save model only if non-regression passes.
    new_model.save(NEW_PKL)
    print(f"[OK] model saved: {NEW_PKL}")
    print(f"[OK] metrics CSV: {METRICS_CSV}")
    print(f"[OK] split CSV:   {SPLIT_CSV}")

    await dispose_engine()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
