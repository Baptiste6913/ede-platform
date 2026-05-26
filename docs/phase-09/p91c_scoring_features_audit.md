# P9.1c-[G-2] — Phase-6 scoring features audit

Empirical confirmation, on the live DB, that the P9.1c pricing work
(`offer_price`, `offer_price_total_eur`, `pricing_source`, and the
`offer_price_quality_flag` ENUM→TEXT+CHECK migration) does **not**
intersect the Phase-6 V1 scoring feature surface. Hence the [G] re-fit can
only be a token non-regression artifact, not a signal-improving training.

Source of truth: `src/scoring/features.py::extract_cluster_features`
(reads only the deal columns enumerated below). Reproducible via
`scripts/audit_p91c_scoring_features.py` → `data/audits/p91c_scoring_features_audit.csv`.

## 1. Exhaustive feature list (13)

`features.py` emits one feature row per **cluster** = distinct
`(target_name, juridiction)` group. The 128 labelled clusters (FR 57 +
IT 35 + DE 36) come from the 222 labelled deals (multi-stage FR filings
collapse into 57 FR clusters).

| # | feature | type | source | extraction logic |
|--:|---|---|---|---|
| 1 | `bid_premium_pct` | numeric | `Deal.premium_pct` × 100, clipped [-50, 500] | first non-null across cluster rows |
| 2 | `relative_size` | numeric | **hardcoded `NaN`** (line 265) | "phase 8+ feature" — never populated |
| 3 | `min_acceptance_threshold` | numeric | `Deal.min_acceptance_threshold` | first non-null across cluster rows |
| 4 | `days_to_expected_close` | numeric | `max(Deal.expected_close_date) − first.announcement_date`, clipped [0, 730] | latest close date in cluster |
| 5 | `events_count` | numeric | `len(rows)` | cluster size (count of filings) |
| 6 | `deal_type` | categorical | `Deal.deal_type` | first row of cluster |
| 7 | `payment_type` | categorical | derived: `"stock" if deal_type in {"ope","opas"} else "cash"` | first row of cluster |
| 8 | `jurisdiction` | categorical | cluster key | constant per cluster |
| 9 | `target_sector` | categorical | **hardcoded `"unknown"`** (line 272) | "phase 8+ feature (GICS)" — never populated |
| 10 | `acquirer_type` | categorical | `_classify_acquirer(acquirer_name)` token search → {`pe`, `soe`, `corporate`, `family`, `unknown`} | most-informative acquirer_name in cluster (skips `[pending parse]`) |
| 11 | `cross_border` | boolean | `_is_cross_border(target_name, acquirer_name)` token search | same acquirer_name as 10 |
| 12 | `has_irrevocable_undertaking` | boolean | **hardcoded `False`** (line 275) | "phase 7+ feature (PDF text scan)" — never populated |
| 13 | `fdi_risk_flag` | boolean | `_fdi_risk(acquirer_name)` token search | same acquirer_name as 10 |

The only deal columns read are: `target_name`, `juridiction`,
`announcement_date`, `acquirer_name`, `premium_pct`,
`min_acceptance_threshold`, `expected_close_date`, `deal_type`,
`completion_label` (label, not feature), `id` (representative).

## 2. Populated-ratio per ingredient (labelled clusters)

`bool_or(column IS NOT NULL)` aggregated per `(target_name, juridiction)`.
Cluster-level because `_first_non_null` propagates any non-null inside the
cluster to the feature.

| jur | clusters | premium_pct | min_acc_threshold | expected_close_date | deal_type | acquirer (non-pending) |
|---|--:|--:|--:|--:|--:|--:|
| FR | 57 | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%)** | 57 (100%) | 20 (35.1%) |
| IT | 35 | **0 (0.0%)** | **0 (0.0%)** | 35 (100%) | 35 (100%) | 31 (88.6%) |
| DE | 36 | **0 (0.0%)** | **0 (0.0%)** | 5 (13.9%) | 36 (100%) | 36 (100%) |
| **ALL** | **128** | **0 (0.0%)** | **0 (0.0%)** | 40 (31.3%) | 128 (100%) | 87 (68.0%) |

### Reading

- **`bid_premium_pct` is a dead feature universally.** 0/128 clusters
  carry a `premium_pct`. No parser populates it today (known issue,
  `docs/scoring/known_issues.md`, P9.1b). The training pipeline's
  `IterativeImputer` resolves NaN to the column mean — i.e. a single
  constant for every row → zero discriminatory power.
- **`min_acceptance_threshold` is a dead feature universally.** Same as
  above; no parser extracts the "X% Mindestannahmequote" clause yet.
- **`days_to_expected_close` is functionally a jurisdiction-correlated
  signal**, not an independent feature: 100% available on IT, ~0% on
  FR and DE. The model effectively learns "IT cluster ↔ has a non-NaN
  days_to_close" which is collinear with `jurisdiction=IT`.
- **`deal_type` is the only universally-populated numeric/categorical
  ingredient.** It also drives `payment_type` via the cash/stock map.
- **`acquirer_name` populates ~68%** but mostly fails on FR (35%
  non-pending) — the AMF BDIF multi-stage parsing leaves the early-stage
  rows at `[pending parse]`. The cluster-level fallback rescues 20/57 FR
  via later filings.

### Hardcoded dead features (3)

`relative_size`, `target_sector`, `has_irrevocable_undertaking` are
returned as constants (`NaN`, `"unknown"`, `False`) for the entire
universe. Same imputation logic as the dead numeric features:
information-free at training time.

### Effective live signal surface (10 features minus dead = ~5–6)

`deal_type`, `payment_type`, `jurisdiction`, `acquirer_type`,
`cross_border`, `fdi_risk_flag`, `events_count`, plus partial
`days_to_expected_close`. The baseline AUC ≈ 0.611 reported on
`scoring_v1_20260520` is consistent with this thin signal.

## 3. P9.1c-touched columns vs scoring (THE point)

Columns introduced or repopulated by P9.1c-[A]–[F] + P9.1c-bis on the 222
labelled deals:

| column | populated / 222 | consumed by `features.py`? |
|---|--:|:--|
| `offer_price` | 68 (30.6%) | ❌ no |
| `offer_price_total_eur` | 1 (0.5%) | ❌ no |
| `offer_price_quality_flag` | 222 (100% — migration default + parser fills) | ❌ no |
| `pricing_source` | 222 (100% — migration default `pdf_parser`) | ❌ no |

`grep -rn 'offer_price\|offer_price_total_eur\|offer_price_quality_flag\|pricing_source\|target_close' src/scoring/` returns **zero matches**.
Same grep on `scripts/score_deals_run.py` returns **zero matches**.

→ **No code path in the scoring pipeline reads any column that P9.1c
modified.** The COALESCE patch sketched in the [G] brief
(`COALESCE(offer_price, offer_price_total_eur)`) has nothing to apply on.

### Note on the singleton `offer_price_total_eur` (1/222)

Of the 2 BaFin mixed-cash-and-stock deals where
`offer_price_total_eur` was computed in P9.1c-[E] (Commerzbank 31.07 €,
ProSieben 5.64 €), only one carries a `completion_label`. The other is
either pending (deal not yet resolved) or excluded from the labelled set
at clustering time. Either way: not a scoring input for V1.

## 4. Implication for [G]

The Phase-6 re-fit at [G] cannot change the training data:

1. **Feature vector unchanged.** Every column read by
   `extract_cluster_features` has the same value pre- and post-P9.1c.
2. **Universe unchanged.** Scoring is flag-agnostic in V1 (per
   `p91b_decisions.md`), so the new `manual_review` flag on 9 DE deals
   does not remove them from training. The only change vs the baseline
   run is the **test-set exclusion** of those 9 deals (user-specified
   for [G] to avoid grading the model on parser-only data).
3. **Hyperparams / class_weight / algorithm unchanged** (brief
   constraint).

→ Expected delta on Brier / AUC: **~0**, modulo the test-set composition
change (9 fewer DE deals in the 213-deal test split). Any |ΔBrier| > 0.005
or |ΔAUC| > 0.01 would be a *side-effect bug* (split seed drift,
imputer-fit-on-different-set, label leakage), **not** a P9.1c gain.

## 5. What this audit DOES NOT cover

- It does not claim the scoring V1 is correct, only that P9.1c left it
  untouched. The thin signal surface (5–6 live features) is real and
  documented as P9.1e debt.
- The 222→128 cluster collapse uses `(target_name, juridiction)`; a
  target-name typo or normalization issue would split a cluster
  artificially. Not investigated here — out of [G] scope.
- `acquirer_name` token-based `acquirer_type` / `cross_border` /
  `fdi_risk_flag` heuristics are not validated against ground truth
  here; P9.1e is the natural place to harden them.

## 6. Decision

Proceed with [G-3] as a **token re-fit** for non-regression record. Stop
and surface to user if the metric delta exceeds the tolerance band.
