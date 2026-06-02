# Phase 12 — V2 retrain: premium_pct coefficient analysis

Retrained the V1 architecture (LogReg ElasticNet l1_ratio=0.5, IterativeImputer, CalibratedClassifierCV isotonic cv=3, random_state=42) on 128 labelled clusters, now that Phase 11 populated `bid_premium_pct` on **25** of them. V2 is NOT promoted; V1 stays in prod.

## Headline — does premium_pct carry signal?

- Column survived IterativeImputer: **True** (V1: dropped, all-NaN).
- `bid_premium_pct` coefficient (full-data ElasticNet): **-0.6692**.
- ElasticNet zeroed it (|coef| < 1e-06): **False**.
- Importance rank by |coef|: **9 / 27** features.
- Sign reading: negative (higher premium → completion less likely).

## Cross-fold stability (TimeSeriesSplit, temporal)

NB: the brief's `gap=90` is a 90-*day* notion; TimeSeriesSplit gaps are in samples, infeasible at ~120 samples / 3 folds, so an expanding-window split with no gap is used. Early folds hold few premium values.

| Fold | non-NaN premium in train | coefficient |
|---|---:|---:|
| 1 | 6 | -1.4593 |
| 2 | 10 | -1.2262 |
| 3 | 15 | -0.5630 |

## Top features by |coefficient| (full-data refit)

| Rank | Feature | Coefficient |
|---|---|---:|
| 1 | `deal_type_opa_simplifiee` | -1.9717 |
| 2 | `acquirer_type_family` | -1.8127 |
| 3 | `jurisdiction_FR` | -1.1708 |
| 4 | `deal_type_opa` | +0.9145 |
| 5 | `deal_type_ope` | -0.8949 |
| 6 | `acquirer_type_corporate` | +0.8688 |
| 7 | `payment_type_cash` | +0.8302 |
| 8 | `payment_type_stock` | -0.8034 |
| 9 | `bid_premium_pct` ⭐ | -0.6692 |
| 10 | `days_to_expected_close` | -0.5743 |
| 11 | `jurisdiction_IT` | +0.3715 |
| 12 | `deal_type_opa_volontaire_totalitaria` | +0.2525 |

## Secondary metrics — IN-SAMPLE, optimistic (do NOT read as the CV baseline)

Eval slice = 117 clusters (labelled - manual_review), scored by the same model that trained on them. These are **in-sample** numbers (near-perfect) and are NOT comparable to the out-of-sample CV baseline (V1 AUC 0.6105, Brier 0.1731). Only the V1→V2 *direction* is weakly informative, and even that is noise-dominated at 25-cluster premium coverage. The coefficient analysis above is the real result, not this table.

| Metric (in-sample) | V1 | V2 | Δ |
|---|---:|---:|---:|
| AUC | 0.9474 | 0.9604 | +0.0130 |
| Brier | 0.0377 | 0.0313 | -0.0064 |
## Verdict

**SIGNAL PRESENT (sparse).** A non-zero coefficient with a consistent sign across folds — premium_pct carries signal even at 25-cluster (39-deal) coverage. Investing in Option B (Growth + offer_price coverage) is justified.
