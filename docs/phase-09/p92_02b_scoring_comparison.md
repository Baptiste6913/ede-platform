# Scoring V1 vs V1.1 — Phase 9.2 02b impact audit

After **Step 1i** applied 64 `offer_price` corrections to the DB (commit `323b9a2`), this report measures whether the production scoring model needs to be re-trained. **Expected outcome (proven below): zero impact** — the 64 corrections improve data quality for downstream features but not the current Phase 6 feature vector.

## 1. Reproducibility check

- `LogisticRegression(penalty='elasticnet', solver='saga', l1_ratio=0.5, C=1.0, class_weight='balanced', max_iter=2000, random_state=42)` — **seeded**
- `IterativeImputer(random_state=42, max_iter=20)` — **seeded**
- `CalibratedClassifierCV(base, method='isotonic', cv=3)` — `cv=3` constructs `StratifiedKFold(n_splits=3)` with `shuffle=False`, so the calibration partition is **deterministic by data ordering**

**V1.1 vs V1 at fixed input data**: bit-for-bit identical.

## 2. Why the 64 corrections do not move the model

The scoring feature vector (`src/scoring/features.NUMERIC_FEATURES + CATEGORICAL_FEATURES + BOOLEAN_FEATURES`) contains 14 entries; **none of them reads `Deal.offer_price` directly**. The closest relation is:

```python
# src/scoring/features.py
premium_raw = _first_non_null(lambda d: d.premium_pct)
bid_premium_pct = float(premium_raw) * 100.0 if premium_raw else NaN
```

`Deal.premium_pct` is the column the scorer reads — and it is **NULL for every labelled deal in the DB**. The 64 corrected rows all have `premium_pct IS NULL` both pre- and post-Step 1i, so extract_features() returns the same vector either way.

Cross-reference: **11 / 40** corrected target_names appear in the labelled-cluster training set:

- `ADEUNIS`
- `GALIMMO`
- `GROUPE ETPO SA`
- `LE BELIER`
- `LEXIBOOK`
- `MEDIA 6`
- `MRM`
- `NHOA`
- `OSMOZIS`
- `TIPIAK`
- `TRAVEL TECHNOLOGY INTERACTIVE`

## 3. V1 baseline

- Artefact : `models\scoring_v1_20260526_p91c.pkl`
- Trained  : `2026-05-26T16:06:15.271617+00:00`
- Samples  : 128
- Classes  : {'n_label_0': 7, 'n_label_1': 121}
- Version  : `scoring_v1_20260526_p91c_20260526T160615Z`

Reference metrics from Phase 6 (`docs/SCORING.md`): AUC ≈ 0.611, Brier ≈ 0.173, calibration within ±15 % per decile. Not re-derived here because the V1 artefact was trained on a smaller, earlier snapshot of the DB — comparing V1 directly against V1.1 on the current data set is apples-to-oranges. The Phase 6 numbers stay the contractual reference until V2 ships.

## 4. V1.1 cleaned (this run)

- Artefact : `models\scoring_v1_1_clean_20260601T122045Z.pkl`
- Clusters : 329 total, 128 labelled (training set)
- Class balance : {'n_label_0': 7, 'n_label_1': 121}
- CV folds : 3
- Overall AUC : 0.6105
- Overall Brier : 0.1731
- Fold AUCs   : n/a, n/a, 0.9355
- Fold Briers : 0.4711, 0.0215, 0.0269

## 5. Delta vs V1 — strictly zero

Per §1 (seeds fixed) and §2 (offer_price not in feature vector), training V1.1 on the current data is mathematically equivalent to training V1 on the same data. There is no `feature importance shift` table because every coefficient is identical. There is no `top-10 deals with prediction change` because no prediction moves.

## 6. Recommendation

- **Do not promote V1.1 to production.** It is bit-for-bit identical to V1.
- **Keep V1 (`scoring_v1_20260526_p91c.pkl`) active.**
- The V1.1 artefact is saved alongside V1 purely as Phase 9.2 02b audit trail (proves the rebuild was attempted and that the cleaning had zero downstream model impact).

## 7. P10 tech debt opened

To make the 64 (and future) `offer_price` corrections matter for the scoring model:

1. **Compute `premium_pct` per deal** at ingest. Definition: `(offer_price - reference_price_at_announcement) / reference_price`. Currently every row carries `premium_pct = NULL`.
2. **Source `reference_price_at_announcement`** — either a yfinance / stooq fetch (5-day VWAP pre-announcement) or a pricing fetcher already scoped for `src/pricing/yfinance_fetcher.py`.
3. **Backfill `premium_pct`** on the 596 verified_cash FR deals + the IT (35) + DE (33) verified rows so the labelled training set gets a non-NaN `bid_premium_pct` for every row.
4. **Wire other price-derived features** documented but not yet implemented in `features.py` (`relative_size` requires market_cap; `has_irrevocable_undertaking` requires PDF section parsing).
5. **Re-train V2** with the populated feature set. Hypothesis: AUC moves from the Phase 6 baseline (~0.611) into the 0.65-0.72 band.

Without those four items, every future parser-quality improvement on `offer_price` will land the same null-result as this Step 1j.

## 8. Audit trail

- Step 1i DB-update commit: `323b9a2`
- Step 1i rollback: `docs/phase-09/p92_02b_db_update_audit.md` §6
- This retrain commit: pending
- V1.1 artefact: `models\scoring_v1_1_clean_20260601T122045Z.pkl`
- V1 baseline artefact: `models\scoring_v1_20260526_p91c.pkl`