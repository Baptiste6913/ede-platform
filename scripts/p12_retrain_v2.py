"""P12 — V2 retrain + premium_pct coefficient analysis (Option A falsification).

premium_pct is already wired into feature extraction as ``bid_premium_pct``
(src/scoring/features.py). In V1 it was NaN for every deal, so IterativeImputer
dropped the column entirely — no coefficient existed. Phase 11 populated 39
deals, so the column now survives and gets a coefficient.

The headline is NOT AUC (too noisy on 39 real / 183 imputed). It is:
1. The bid_premium_pct coefficient in the full-data ElasticNet LogReg
   (non-zero? sign? rank vs the other features?).
2. Its cross-fold stability (TimeSeriesSplit, temporal).
3. Whether ElasticNet's L1 penalty zeroed it (a verdict in itself).

AUC / Brier vs V1 are logged as secondary, noisy context.

V2 is NOT promoted — V1 stays in prod. Outputs:
- ``models/scoring_v2_premium_{ts}.pkl``
- ``docs/phase-12/v2_coefficient_analysis.md``

Run (repo root, postgres up):
  DATABASE_URL=postgresql+asyncpg://ede:ede@localhost:5432/ede \
    .venv/Scripts/python.exe scripts/p12_retrain_v2.py
"""

from __future__ import annotations

import asyncio
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.db import dispose_engine, get_engine
from src.core.models import Deal
from src.scoring.features import iter_all_clusters
from src.scoring.model import ScoringModel, _build_estimator, clusters_to_dataframe

REPO_ROOT = Path(__file__).resolve().parents[1]
V1_PKL = REPO_ROOT / "models" / "scoring_v1_20260526_p91c.pkl"
OUT_MD = REPO_ROOT / "docs" / "phase-12" / "v2_coefficient_analysis.md"

TARGET = "bid_premium_pct"
V1_AUC = 0.6105
V1_BRIER = 0.1731
N_SPLITS = 3
ZERO_TOL = 1e-6


def _post_names(pipeline) -> list[str]:  # type: ignore[no-untyped-def]
    pre = pipeline.named_steps["pre"]
    raw = list(pre.get_feature_names_out())
    return [n.split("__", 1)[1] if "__" in n else n for n in raw]


def _coef_of(names: list[str], coefs: np.ndarray, feature: str) -> float | None:
    return float(coefs[names.index(feature)]) if feature in names else None


async def _excluded_keys(session) -> set[tuple[str, str]]:  # type: ignore[no-untyped-def]
    rows = (
        await session.execute(
            select(Deal.target_name, Deal.juridiction)
            .where(Deal.offer_price_quality_flag == "manual_review")
            .where(Deal.completion_label.is_not(None))
            .distinct()
        )
    ).all()
    return set(rows)


def _metrics(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    auc = float(roc_auc_score(y, p)) if len(np.unique(y)) >= 2 else float("nan")
    return auc, float(brier_score_loss(y, p))


async def main() -> int:
    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        clusters = await iter_all_clusters(session)
        excluded = await _excluded_keys(session)

    X, y, labelled_idx = clusters_to_dataframe(clusters)
    X_train = X.iloc[labelled_idx].reset_index(drop=True)
    keys = [(clusters[i].target_name, clusters[i].jurisdiction) for i in labelled_idx]
    ann = [clusters[i].earliest_announcement for i in labelled_idx]
    n_premium = int(X_train[TARGET].notna().sum())
    print(f"[P12] labelled clusters: {len(labelled_idx)} | non-NaN {TARGET}: {n_premium}")

    # ---- Full-data V2 ----
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    v2 = ScoringModel(version=f"scoring_v2_premium_{ts}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        v2.fit(X_train, y)

    names = v2.feature_names_post_transform
    coefs = v2.inner_clf.coef_[0]  # type: ignore[union-attr]
    premium_coef = _coef_of(names, coefs, TARGET)
    kept = TARGET in names
    zeroed = kept and premium_coef is not None and abs(premium_coef) < ZERO_TOL

    # Rank by |coef| across all post-transform features.
    ranking = sorted(zip(names, coefs, strict=True), key=lambda kv: abs(kv[1]), reverse=True)
    rank = next((i + 1 for i, (n, _) in enumerate(ranking) if n == TARGET), None)

    # ---- Cross-fold stability (temporal) ----
    order = np.argsort(ann)
    Xs = X_train.iloc[order].reset_index(drop=True)
    ys = y[order]
    fold_coefs: list[float | None] = []
    fold_nprem: list[int] = []
    for tr, _te in TimeSeriesSplit(n_splits=N_SPLITS).split(Xs):
        fold_nprem.append(int(Xs.iloc[tr][TARGET].notna().sum()))
        pipe = _build_estimator()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pipe.fit(Xs.iloc[tr], ys[tr])
        fold_coefs.append(_coef_of(_post_names(pipe), pipe.named_steps["clf"].coef_[0], TARGET))

    # ---- Secondary: AUC/Brier vs V1 (eval slice = labelled - manual_review) ----
    v1 = ScoringModel.load(V1_PKL)
    mask = np.array([k not in excluded for k in keys])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p_v1 = v1.predict_proba(X_train)[:, 1][mask]
        p_v2 = v2.predict_proba(X_train)[:, 1][mask]
    y_eval = y[mask]
    auc_v1, brier_v1 = _metrics(y_eval, p_v1)
    auc_v2, brier_v2 = _metrics(y_eval, p_v2)

    v2_pkl = REPO_ROOT / "models" / f"scoring_v2_premium_{ts}.pkl"
    v2.save(v2_pkl)

    _write_md(
        n_labelled=len(labelled_idx),
        n_premium=n_premium,
        kept=kept,
        zeroed=zeroed,
        premium_coef=premium_coef,
        rank=rank,
        total_feats=len(names),
        ranking=ranking,
        fold_coefs=fold_coefs,
        fold_nprem=fold_nprem,
        auc_v1=auc_v1,
        auc_v2=auc_v2,
        brier_v1=brier_v1,
        brier_v2=brier_v2,
        n_eval=int(mask.sum()),
        v2_pkl=v2_pkl.name,
    )

    print(
        f"[P12] {TARGET}: kept={kept} zeroed={zeroed} coef={premium_coef} rank={rank}/{len(names)}"
    )
    print(f"[P12] fold coefs: {fold_coefs} (non-NaN premium per fold: {fold_nprem})")
    print(f"[P12] AUC V1={auc_v1:.4f} V2={auc_v2:.4f} | Brier V1={brier_v1:.4f} V2={brier_v2:.4f}")
    print(f"[P12] model: {v2_pkl}")
    print(f"[P12] MD: {OUT_MD}")
    await dispose_engine()
    return 0


def _verdict(kept: bool, zeroed: bool, coef: float | None, folds: list[float | None]) -> str:
    if not kept or zeroed or coef is None:
        return (
            "**SIGNAL ABSENT / ZEROED.** ElasticNet dropped or zeroed "
            "`bid_premium_pct`. On this coverage the feature carries no usable "
            "signal — Option B (widen coverage) is required to retest, not "
            "optional."
        )
    present = [c for c in folds if c is not None]
    same_sign = bool(present) and len({c > 0 for c in present}) == 1
    if same_sign and len(present) >= 2:
        return (
            "**SIGNAL PRESENT (sparse).** A non-zero coefficient with a "
            "consistent sign across folds — premium_pct carries signal even at "
            "25-cluster (39-deal) coverage. Investing in Option B (Growth + "
            "offer_price coverage) is justified."
        )
    return (
        "**INDETERMINATE.** Non-zero on full data but unstable / sign-flipping "
        "across folds (sparsity-driven). Option B is needed to decide."
    )


def _write_md(**k: object) -> None:
    coef = k["premium_coef"]
    folds = k["fold_coefs"]
    ranking = k["ranking"]
    lines: list[str] = []
    lines.append("# Phase 12 — V2 retrain: premium_pct coefficient analysis\n")
    lines.append(
        f"Retrained the V1 architecture (LogReg ElasticNet l1_ratio=0.5, "
        f"IterativeImputer, CalibratedClassifierCV isotonic cv=3, random_state=42) "
        f"on {k['n_labelled']} labelled clusters, now that Phase 11 populated "
        f"`bid_premium_pct` on **{k['n_premium']}** of them. V2 is NOT promoted; "
        "V1 stays in prod.\n"
    )

    lines.append("## Headline — does premium_pct carry signal?\n")
    lines.append(f"- Column survived IterativeImputer: **{k['kept']}** (V1: dropped, all-NaN).")
    coef_str = f"{coef:+.4f}" if isinstance(coef, float) else "n/a (dropped)"
    lines.append(f"- `bid_premium_pct` coefficient (full-data ElasticNet): **{coef_str}**.")
    lines.append(f"- ElasticNet zeroed it (|coef| < {ZERO_TOL:.0e}): **{k['zeroed']}**.")
    lines.append(f"- Importance rank by |coef|: **{k['rank']} / {k['total_feats']}** features.")
    sign = ""
    if isinstance(coef, float) and abs(coef) >= ZERO_TOL:
        sign = (
            "positive (higher premium → completion more likely)"
            if coef > 0
            else ("negative (higher premium → completion less likely)")
        )
        lines.append(f"- Sign reading: {sign}.")
    lines.append("")

    lines.append("## Cross-fold stability (TimeSeriesSplit, temporal)\n")
    lines.append(
        "NB: the brief's `gap=90` is a 90-*day* notion; TimeSeriesSplit gaps are "
        "in samples, infeasible at ~120 samples / 3 folds, so an expanding-window "
        "split with no gap is used. Early folds hold few premium values.\n"
    )
    lines.append("| Fold | non-NaN premium in train | coefficient |")
    lines.append("|---|---:|---:|")
    for i, (c, npm) in enumerate(zip(folds, k["fold_nprem"], strict=True), start=1):  # type: ignore[arg-type]
        cstr = f"{c:+.4f}" if isinstance(c, float) else "dropped (all-NaN)"
        lines.append(f"| {i} | {npm} | {cstr} |")
    lines.append("")

    lines.append("## Top features by |coefficient| (full-data refit)\n")
    lines.append("| Rank | Feature | Coefficient |")
    lines.append("|---|---|---:|")
    for i, (n, c) in enumerate(ranking[:12], start=1):  # type: ignore[index]
        mark = " ⭐" if n == TARGET else ""
        lines.append(f"| {i} | `{n}`{mark} | {c:+.4f} |")
    lines.append("")

    lines.append("## Secondary metrics — IN-SAMPLE, optimistic (do NOT read as the CV baseline)\n")
    lines.append(
        f"Eval slice = {k['n_eval']} clusters (labelled - manual_review), scored "
        "by the same model that trained on them. These are **in-sample** numbers "
        "(near-perfect) and are NOT comparable to the out-of-sample CV baseline "
        f"(V1 AUC {V1_AUC}, Brier {V1_BRIER}). Only the V1→V2 *direction* is "
        "weakly informative, and even that is noise-dominated at "
        f"{k['n_premium']}-cluster premium coverage. The coefficient analysis "
        "above is the real result, not this table.\n"
    )
    lines.append("| Metric (in-sample) | V1 | V2 | Δ |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| AUC | {k['auc_v1']:.4f} | {k['auc_v2']:.4f} | {k['auc_v2'] - k['auc_v1']:+.4f} |"  # type: ignore[operator]
    )
    lines.append(
        f"| Brier | {k['brier_v1']:.4f} | {k['brier_v2']:.4f} | "  # type: ignore[operator]
        f"{k['brier_v2'] - k['brier_v1']:+.4f} |"
    )

    lines.append("## Verdict\n")
    lines.append(
        _verdict(
            bool(k["kept"]), bool(k["zeroed"]), coef if isinstance(coef, float) else None, folds
        )
    )  # type: ignore[arg-type]
    lines.append("")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
