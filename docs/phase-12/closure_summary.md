# Phase 12 (Step A) — Closure: premium_pct signal falsification

## Objective

Fast falsification: now that Phase 11 populated `premium_pct` (39 deals → 25
labelled clusters), does the feature carry usable signal for deal completion —
or is it noise that ElasticNet's L1 penalty discards? The headline is the
**coefficient**, not AUC (un-measurable out-of-sample at this coverage).

## Result — SIGNAL PRESENT (sparse)

| Check | Value |
|---|---|
| Column survives IterativeImputer | **True** (V1: dropped, all-NaN) |
| `bid_premium_pct` coefficient (full-data ElasticNet) | **−0.6692** |
| Zeroed by L1 (\|coef\| < 1e-6) | **No** |
| Importance rank by \|coef\| | **9 / 27** features |
| Cross-fold sign (TimeSeriesSplit, 3 folds) | **−1.46 / −1.23 / −0.56 → all negative** |
| Premium coverage | **25 / 128 labelled clusters** (39 deals) |

ElasticNet kept the feature (it could have zeroed it — and zeroed nothing else
of note around it), at rank 9/27, ahead of `days_to_expected_close`. The sign is
**consistently negative across all three temporal folds**. This is a successful
falsification: the "premium_pct is noise" hypothesis is **not** supported.

## Interpreting the negative sign (hypothesis, not conclusion)

Higher premium → *lower* completion probability. The economically coherent
reading: the bid premium over the T-1 reference is a **risk proxy, not a
generosity proxy**. A large gap between offer and pre-bid price means the market
had *not* priced the deal in — completion was uncertain (financing, regulatory,
contested terms). Small premiums are second-step / squeeze-out offers already
trading near the bid, where completion is near-certain. So a negative coefficient
fits M&A-arb intuition once "premium" is read as "spread = unpriced risk".

This is a **hypothesis to validate on more data**, not a settled result.

## Explicit reservations

1. **25 clusters is very thin.** The coefficient is real but its *magnitude* is
   unstable (−0.56 to −1.46 across folds). We can confirm direction, not size.
2. **AUC is in-sample and un-usable.** V1 0.9474 → V2 0.9604 is in-sample
   (the model scores the clusters it trained on) and is NOT the out-of-sample CV
   baseline (V1 CV AUC 0.6105). A real CV AUC needs more premium coverage.
3. **The negative sign is counter-intuitive** versus the naive "premium =
   generous offer = completion" prior. The risk-proxy reading above must be
   confirmed before the feature is trusted in production.

## Decision — GO Option B

Widen `premium_pct` coverage to ~80–100 clusters (Euronext Growth identity
cross-check + offer_price parsing fixes + a few no_price_data recoveries) to
obtain (a) a stable coefficient magnitude and (b) a genuine out-of-sample CV AUC
that can quantify the lift over V1.

**V2 is NOT promoted.** V1 (`scoring_v1_20260526_p91c.pkl`) stays in prod until
Option B delivers a measurable, validated lift.

## Tech debt (Phase 13+, unchanged from Phase 11 closure)

1. offer_price parsing (COVIVIO 3.00, VOGO +556 %, ALBA −87 %).
2. no_price_data recovery (CompuGroup COP.DE has no Yahoo data → find the real
   symbol).
3. Euronext Growth safe resolution (shortName cross-check / ISIN→mnemonic map).
4. unknown_exch venue mapping extension.
5. IT/Consob ISIN extraction (blocks all IT upstream).

## Commits

| Phase | Commit | Summary |
|---|---|---|
| 12 Step A | `10abb20` | retrain V2 + premium_pct coefficient analysis |
| 12 closure | _this_ | signal confirmed (sparse), Option B justified |

## Artifacts

- `docs/phase-12/v2_coefficient_analysis.md` — full coefficient + fold table.
- `models/scoring_v2_premium_20260602T105515Z.pkl` — V2 (NOT promoted).
- `scripts/p12_retrain_v2.py` — reproducible retrain + analysis.
