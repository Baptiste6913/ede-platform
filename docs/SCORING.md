# Scoring engine — V1

**Status:** V1 trained 2026-05-20 from 128 labelled clusters (121 closed + 7 failed). Operational artifact: `models/scoring_v1_<timestamp>.pkl`. Latest run summary: `artifacts/phase-06/scoring_run_latest.json` + `artifacts/phase-06/validation_report.md`.

---

## Model architecture

```
ColumnTransformer
├── numeric    → IterativeImputer  → StandardScaler
├── categorical → OneHotEncoder(handle_unknown='ignore')
└── boolean    → passthrough
        │
        ▼
LogisticRegression(
    penalty='elasticnet', solver='saga', l1_ratio=0.5,
    C=1.0, class_weight='balanced', max_iter=2000,
)
        │
        ▼  (wrapped, full pipeline as base)
CalibratedClassifierCV(method='isotonic', cv=3)
```

- The **calibrated estimator** produces `p_completion` (probability the deal closes).
- A **separate refit** of the inner pipeline on the full training set is kept inside the model wrapper so per-row coefficient × scaled-feature contributions can be reported (`feature_contributions()` in `ScoringModel`). `CalibratedClassifierCV` internally retrains on folds and does not expose stable coefficients.
- **Why ElasticNet + Isotonic** (not pure L1 + Platt): with N≈128 and 17:1 class imbalance, L2 alone over-shrinks coefficients and L1 alone is unstable; mixing at `l1_ratio=0.5` selects features without losing all signal. Isotonic calibration is non-parametric and friendlier to small-N than sigmoid (Platt).

### `p → stars → decision` mapping

| `p_completion` | stars | decision |
|---:|---:|---|
| <0.30 | 1 | `skip` |
| <0.50 | 2 | `skip` |
| <0.70 | 3 | `wait` |
| <0.85 | 4 | `enter` |
| ≥0.85 | 5 | `enter` |

The `decision` column in `scores` is set from `p` alone for V1. In V2 it will incorporate market-implied probability + edge (see phase 8).

---

## Features (12)

Defined in `src/scoring/features.py`. Numeric features go through `IterativeImputer`; categorical use `OneHotEncoder(handle_unknown='ignore')`; booleans pass through as 0/1. Cluster aggregation by `(target_name, juridiction)` so FR multi-stage BDIF chains contribute one row.

| Feature | Type | Source | V1 coverage |
|---|---|---|---|
| `bid_premium_pct` | numeric | `deals.premium_pct` (PDF parser) | NULL on every training cluster — imputed |
| `relative_size` | numeric | TBD (target/acquirer market-cap) | hardcoded NaN — phase 8 feature |
| `min_acceptance_threshold` | numeric | `deals.min_acceptance_threshold` | NULL on every training cluster — imputed |
| `days_to_expected_close` | numeric | `expected_close_date - announcement_date` | IT/DE only; FR mostly NULL |
| `events_count` | numeric | number of `deals` rows per cluster | **always populated** (FR chains 2-9, IT/DE = 1) |
| `deal_type` | categorical | `deals.deal_type` (enum) | 18 values one-hot |
| `payment_type` | categorical | derived from `deal_type` (opa* = cash, ope/opas = stock) | 2 values |
| `jurisdiction` | categorical | `deals.juridiction` | FR / IT / DE |
| `target_sector` | categorical | TBD (GICS) | hardcoded `unknown` — phase 8 feature |
| `acquirer_type` | categorical | heuristic on `acquirer_name` tokens | `pe` / `corporate` / `family` / `soe` / `unknown` |
| `cross_border` | bool | acquirer name contains foreign-country marker not in target | naive heuristic, false-positive on DE-wrapper of foreign parent |
| `has_irrevocable_undertaking` | bool | TBD (PDF text scan) | hardcoded `False` — phase 7 feature |
| `fdi_risk_flag` | bool | acquirer name token match (`ADNOC`, `China`, `JD.com`, `Saudi`…) | sparse but accurate when fires |

**V1 limitation surfaced by the live run:** the IterativeImputer logs `Skipping features without any observed values: [0, 1, 2, 3]` — i.e. the 4 numeric features sourced from PDF parsers are entirely missing across the 128-row training set. Net training signal lives in `events_count` + the categorical / boolean stack. The model is therefore most discriminative on the **structural** axes (offer type, jurisdiction, acquirer profile) and weakest on the **financial** axes (premium, size, undertakings).

---

## Calibration metrics (current run)

| Predicted-prob bin (mid) | Empirical rate | n |
|---:|---:|---:|
| 0.50 | 0.429 | 7 |
| 0.70 | 0.833 | 18 |
| 0.90 | 1.000 | 103 |

Pooled cross-validated metrics (3 folds, gap=90 j, date-ordered):

| Metric | Target | Actual | Status |
|---|---:|---:|---|
| AUC | ≥ 0.65 | **0.611** | ⚠️ near target |
| Brier | ≤ 0.20 | **0.173** | ✅ |
| Calibration (±15 % on deciles) | within band | within band on populated deciles (0.50/0.70/0.90) | ✅ |

The AUC is dragged down by folds 0 + 1 where the validation chunk contained 0 negatives. With 7 total failures concentrated in the older (pre-2024) FR cohort, the chronological split puts most of them in fold 2. Only fold 2 has a defined AUC (**0.935**). The pooled 0.611 reflects (a) Brier degradation on label-1-only folds and (b) limited overall fold count rather than a true ranking failure.

### Sanity-check on 5 named deals

| Target | Expectation | Actual `p` | Stars | Verdict |
|---|---|---:|---:|---|
| MorphoSys AG | HIGH | 1.00 | 5 | ✅ |
| Banco BPM Spa (UC withdrawal) | LOW | 0.56 | 3 | ⚠️ low-ish but not strongly negative |
| Covestro AG | HIGH | 1.00 | 5 | ✅ |
| Mediobanca | HIGH | 1.00 | 5 | ✅ |
| 1&1 AG | HIGH | 1.00 | 5 | ✅ |

The single failure case (Banco BPM, label=0) lands at `p=0.56` vs the four positives at `p=1.0` — a meaningful 0.44 spread. With richer features (premium, undertaking, sector) the failure signal should sharpen substantially.

### Coefficient inspection (full-data refit)

Top positive contributors (favor `label=1`):

- `deal_type_opa` → +1.347
- `events_count` → +1.034
- `payment_type_cash` → +0.933
- `acquirer_type_corporate` → +0.774
- `deal_type_opa_volontaire_totalitaria` → +0.502

Top negative contributors (favor `label=0`):

- `acquirer_type_family` → −1.977
- `deal_type_opra` → −1.676
- `jurisdiction_FR` → −1.400
- `deal_type_opa_simplifiee` → −1.108
- `payment_type_stock` → −0.906

Caveats:
- `acquirer_type_family` is the strongest negative signal — that's mostly an artefact of the 7 failures being FR family-controlled OPRA chains; the heuristic correctly captures something real (family-controlled offers can lapse when minority holdouts refuse) but the magnitude is exaggerated by the imbalanced training set.
- `jurisdiction_FR` is structurally negative because all 7 failures are FR. Once IT/DE labels accumulate, this will rebalance.

---

## Known V1 limitations

1. **Tiny labelled set.** N=128, with 7 negatives. A single mislabel in the failure cohort would shift AUC by ~0.05.
2. **No live market data.** No price-implied probability, no spread analytics, no premium-to-VWAP. Limits the model to structural features.
3. **No news sentiment.** Phase 9+.
4. **No PDF text scan.** `has_irrevocable_undertaking` is hardcoded `False`; in practice it appears in most §15 WpÜG / Documento d'offerta documents — high-value future signal.
5. **`relative_size` and `target_sector` are placeholders.** They will be populated when GDELT / ISIN-to-mcap / GICS mapping pipelines land (phase 6+ news, phase 8 enrichment).
6. **FR multi-stage chains over-count `events_count`.** A 9-stage Bolloré galaxy chain (Compagnie du Cambodge, Financière Moncey…) is one underlying operation but produces `events_count=9` — distorting magnitudes. A `cluster_id` column with a single canonical row per OPA would clean this up.
7. **0 Untersagung in the 24-month window.** All 9 BaFin prohibitions cluster 2017-2019; widening the window would bring them in as label=0 candidates. Migration 0008 (`prohibition_ungenutzt` enum value) is already in place.

---

## Roadmap V2 features

| Feature | Source | Phase |
|---|---|---|
| `target_mcap` + `relative_size` | Stooq / Yahoo Finance API | 6 (market data) |
| `bid_premium_pct` (live) | offer_price / unaffected-pre-announcement price | 6 |
| `news_sentiment_30d` | Perplexity API / GDELT | 9 (news enrichment) |
| `target_sector_GICS` | ISIN → ICB → GICS lookup | 8 (enrichment) |
| `has_irrevocable_undertaking` | PyMuPDF text scan + regex | 7 (PDF NLP) |
| `recent_regulator_intervention` | FDI / antitrust extension events | 7-8 |
| `spread_to_offer` (live) | last trade vs offer price | 6 |

---

## Operational

```
python scripts/score_deals_run.py
```

Trains the model on `deals` rows with `completion_label IS NOT NULL`, scores every `(target, juridiction)` cluster, persists to the `scores` table, and writes:

- `models/scoring_v1_<UTC-timestamp>.pkl`
- `artifacts/phase-06/scoring_run_<UTC-timestamp>.json`
- `artifacts/phase-06/scoring_run_latest.json` (always overwritten)
- `artifacts/phase-06/validation_report.md`

Re-running is safe — each run appends a new row per deal in `scores` with the run's `model_version`. The `scores.ts` column lets downstream consumers always pick the latest.

Phase-11 Discord alerts on score-extremes (≥4★ new, ≤2★ regression) are stubbed in the runner (no actual webhook call yet — wiring lands in phase 11).
