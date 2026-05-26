"""Phase 9.1c-[G-3.5a] — intra-run variance probe.

Fits ``ScoringModel`` THREE times consecutively on the SAME 128 labelled
clusters with the SAME hyperparameters (``random_state=42`` everywhere
inside ``ScoringModel``), then measures:

  - max pairwise prediction diff between the 3 runs (full set + eval set)
  - Brier and AUC on the 120-cluster eval slice for each run + baseline
  - delta vs baseline AUC

Hypothesis under test: the AUC delta of +0.013 between the May-20 baseline
and the May-26 refit is a ``roc_auc_score`` tie-breaking artifact, not a
model change. If 3 consecutive refits give:
  - prediction max-diff ≪ 1e-10 between all pairs (incl. baseline), AND
  - AUC values that fluctuate by ~0.01

→ hypothesis confirmed: variance is purely metrological (argsort on ties
sensitive to FP-noise of order 1e-15 from BLAS / OpenMP scheduling).

If predictions are byte-identical AND AUC is ALSO byte-identical → the
+0.013 delta would be a real bug (data leak, seed not propagated, ordering
change), and [G-3] would need deeper investigation.

Outputs:
  - ``data/audits/p91c_refit_variance.csv``
  - console table

Run (PowerShell, repo root, postgres up):
  $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
  .venv/Scripts/python.exe scripts/variance_check_p91c.py
"""

from __future__ import annotations

import asyncio
import csv
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.db import dispose_engine, get_engine
from src.core.models import Deal
from src.scoring.features import iter_all_clusters
from src.scoring.model import ScoringModel, clusters_to_dataframe

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PKL = REPO_ROOT / "models" / "scoring_v1_20260520T141111Z.pkl"
OUTPUT = REPO_ROOT / "data" / "audits" / "p91c_refit_variance.csv"

N_REFITS = 3
TWO_CLASSES = 2  # sklearn metrics need >= 2 distinct labels for AUC


async def _excluded_cluster_keys() -> set[tuple[str, str]]:
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


async def main() -> int:
    excluded = await _excluded_cluster_keys()
    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        clusters = await iter_all_clusters(session)

    x_full, y, labelled_idx = clusters_to_dataframe(clusters)
    x_train = x_full.iloc[labelled_idx].reset_index(drop=True)
    labelled_keys = [(clusters[i].target_name, clusters[i].jurisdiction) for i in labelled_idx]
    eval_mask = np.array([key not in excluded for key in labelled_keys])
    y_eval = y[eval_mask]

    print(f"[G-3.5a] clusters loaded: {len(clusters)}, labelled: {len(labelled_idx)}")
    print(f"[G-3.5a] eval slice: {int(eval_mask.sum())} clusters")

    # ---- Baseline predictions ----
    baseline = ScoringModel.load(BASELINE_PKL)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p_baseline = baseline.predict_proba(x_train)[:, 1]

    # ---- 3 fresh refits ----
    predictions: list[np.ndarray] = []
    for run in range(N_REFITS):
        model = ScoringModel(version=f"variance_run_{run + 1}")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(x_train, y)
            p = model.predict_proba(x_train)[:, 1]
        predictions.append(p)
        print(f"[G-3.5a] run {run + 1}/3 fitted, mean p={p.mean():.6f}")

    # ---- Pairwise prediction diffs (baseline vs runs, run vs run) ----
    print()
    print("[diag] Pairwise max |prediction diff| (full set, 128 clusters):")
    all_arrays = {"baseline": p_baseline}
    for i, p in enumerate(predictions):
        all_arrays[f"run_{i + 1}"] = p
    names = list(all_arrays.keys())
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            d = float(np.abs(all_arrays[a] - all_arrays[b]).max())
            print(f"       {a:<10} vs {b:<10}: {d:.3e}")

    # ---- Brier + AUC per run on eval slice ----
    def _eval(p: np.ndarray) -> tuple[float, float]:
        p_eval = p[eval_mask]
        brier = float(brier_score_loss(y_eval, p_eval))
        auc = (
            float(roc_auc_score(y_eval, p_eval))
            if len(np.unique(y_eval)) >= TWO_CLASSES
            else float("nan")
        )
        return brier, auc

    base_brier, base_auc = _eval(p_baseline)
    rows = [
        {
            "run": "baseline",
            "model_version": baseline.version,
            "brier": f"{base_brier:.6f}",
            "auc": f"{base_auc:.6f}",
            "auc_delta_vs_baseline": "+0.000000",
            "auc_delta_vs_run_1": "n/a",
        }
    ]
    p_run1 = predictions[0]
    _, auc1 = _eval(p_run1)
    for i, p in enumerate(predictions):
        brier, auc = _eval(p)
        rows.append(
            {
                "run": f"run_{i + 1}",
                "model_version": f"variance_run_{i + 1}",
                "brier": f"{brier:.6f}",
                "auc": f"{auc:.6f}",
                "auc_delta_vs_baseline": f"{auc - base_auc:+.6f}",
                "auc_delta_vs_run_1": f"{auc - auc1:+.6f}",
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "run",
                "model_version",
                "brier",
                "auc",
                "auc_delta_vs_baseline",
                "auc_delta_vs_run_1",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print("=" * 78)
    print(f"[G-3.5a] Variance: {N_REFITS} consecutive refits + baseline (eval 120 clusters)")
    print("=" * 78)
    header = (
        f"{'run':<10} {'brier':>10} {'auc':>10} "
        f"{'dAUC_base':>12} {'dAUC_run1':>12}"
    )
    print(header)
    print("-" * 78)
    for r in rows:
        print(
            f"{r['run']:<10} "
            f"{r['brier']:>10} "
            f"{r['auc']:>10} "
            f"{r['auc_delta_vs_baseline']:>12} "
            f"{r['auc_delta_vs_run_1']:>12}"
        )
    print()
    aucs_runs = [float(r["auc"]) for r in rows[1:]]
    auc_spread = max(aucs_runs) - min(aucs_runs)
    print(f"[diag] AUC spread across the {N_REFITS} refits: {auc_spread:.6f}")
    print(f"[diag] CSV: {OUTPUT}")

    await dispose_engine()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
