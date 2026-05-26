# Phase 9.1c — closure summary

Closes the P9.1c sprint (BaFin mixed-offer hardening + external pricing
foundation). All checkpoints A→G validated; [H] (PR + CI + merge) is the
operator's responsibility per the [G] brief.

Branch: `phase-09c-yfinance-enrichment` · 23 commits · ready for review.

## 1. Scope delivered

### [A] yfinance ticker mapping (commits `28e4cb4`, `b8ee8d2`)
- yfinance 1.4.0 added to `pyproject.toml` dependencies.
- `scripts/probe_yfinance_mapping.py`: ISIN → Yahoo ticker probe over the
  small-cap BaFin set. 5/5 acquirer + small-cap hits validated against
  live UCG.MI quote.

### [B] Migration 0015 (commit `47b9ec4`)
- `offer_price_quality_flag` converted from Postgres ENUM to `TEXT` + CHECK
  constraint (cheaper to evolve; canonical values in `src/core/enums.py`).
- Added `verified_mixed` flag value.
- Added `offer_price_total_eur NUMERIC(12,4)`.
- Added `pricing_source TEXT` (CHECK: `pdf_parser` | `yfinance_enriched` |
  `manual`) with default `pdf_parser`.
- New table `deal_consideration` (structured cash + share components for
  mixed offers).

### [C] yfinance_fetcher module (commits `1af19a4`, `405ca00`)
- `src/pricing/yfinance_fetcher.py`: `get_close_eur(ticker, target_date,
  *, max_lookback_days=5) -> (Decimal, date) | None`.
- SQLite cache at `data/cache/yfinance.db` (TTL 30 days).
- FX conversion via `EUR<cur>=X` Yahoo pairs.
- Exponential retry 1s / 3s / 9s on transient errors.
- 92 % unit coverage (10 mocked scenarios; vcrpy incompatible with
  yfinance's curl_cffi backend, mocked at `yf.Ticker` boundary).

### [D] Acquirer registry + consideration parsing (commits `4193e33`,
`6551e44`, `544e2f3`, `bf3a40b`)
- `src/pricing/acquirer_registry.py`: UniCredit (UCG.MI) + MFE (MFEA.MI)
  + fuzzy `resolve_acquirer()` substring matcher.
- BaFin parser gains `_extract_consideration()` + `_CONSIDERATION_SHARE_RE`
  regex (`Gewährung/Gegenleistung … von <ratio> (Stück)aktien der
  <Erwerber>`). Emits a `ConsiderationStructured` dataclass.
- `scripts/populate_deal_consideration.py`: backfills the
  `deal_consideration` table for the 2 mixed BaFin offers (Commerzbank,
  ProSieben).

### [E] Total-EUR recalc (commits `92918e3`, `f878a54`, `40cf132`,
`f332730`)
- `src/pricing/target_ticker_resolver.py`: `TARGET_TICKER_MAP` (5 entries)
  + `REJECTED_TICKER_MAPPINGS` (TUR.DE = iShares Turkey ETF, MEN.F = penny
  stock) as anti-regression memo.
- `src/pricing/recalc.py`: `prev_business_day()` + `compute_total_eur(cash,
  ratio, acquirer_close)` quantized to NUMERIC(12,4).
- `scripts/recalc_offer_price_total.py`: populates `offer_price_total_eur`
  on the 2 mixed deals. Commerzbank 31.07 € (cash 5.50 + 0.7026·UCG.MI),
  ProSieben 5.64 € (cash 1.50 + 1.0×MFEA.MI). Both negative spread at T-1bd.
- 16 scenarios covering recalc + target resolver.

### [F] Small-cap external validation (commits `5802b83`, `45fdf42`,
`fe13c50`)
- `scripts/validate_small_caps.py`: 30 % deviation threshold + `--apply`.
- Probe + apply on 12 BaFin small-caps (`offer_price < 5 EUR`):
  - 3 deals confirmed `verified_cash` via yfinance EOD T-1bd cross-check
    (Klassik Radio 2.14 %, CECONOMY 3.37 %, Albis Leasing 7.10 %).
  - 9 deals downgraded to `manual_review` (ticker_unresolved or rejected
    map). Not a parser failure: small-cap targets delisted post-OPA so
    yfinance has no post-announcement history.
- DFV note: 6.60 € is the parser's anchored extraction (post-P9.1a
  par-value fix); manual_review is the absence of an external feed, not a
  parser error.

### P9.1c-bis — non-outlier BaFin re-parse (commits `a83ccb4`, `de7b3c8`)
- Closes the data-hygiene gap from P9.1b decision (4) ("v2-on-new only"):
  the 25 non-outlier DE deals still carried the migration default
  `suspect_low_unverified` flag + `parser_version = 1`.
- `scripts/reparse_p91cbis.py` re-parses all DE deals with `parser_version
  < PARSER_VERSION`. Outcome: **25 / 25 promoted to `verified_cash`,
  0 / 25 price changes**. The parser-v1 first-EUR-match happened to
  match the Geldleistung amount on non-outliers (no par-value line
  preceded). All BaFin deals now at `parser_version = 2`, no parser
  asymmetry within the source.

### [G] Phase-6 re-scoring (commits `8ae7709`, `3d2e017`, `98d9a3e`,
`ec3ef14`, `e47f304`)
- **[G-2] feature audit**: confirmed `src/scoring/features.py` consumes
  ZERO P9.1c-touched columns (offer_price / offer_price_total_eur /
  offer_price_quality_flag / pricing_source). Effective live signal
  surface is ~5–6 features (jurisdiction, deal_type, payment_type,
  events_count, acquirer-derived); the 3 documented dead features
  (`relative_size`, `target_sector`, `has_irrevocable_undertaking`) plus
  `bid_premium_pct` (0/128 populated) and `min_acceptance_threshold`
  (0/128) account for the AUC baseline of 0.611.
- **[G-2.5] sanity check**: clarified the singleton
  `offer_price_total_eur` count in the labelled set (Commerzbank is live
  / `completion_label = NULL`, ProSieben is the 1/222).
- **[G-3.5a] variance probe**: 3 consecutive in-process refits produce
  byte-identical predictions and byte-identical AUC; cross-process noise
  vs the May-20 baseline is 8.2 × 10⁻¹⁵ (1-8 ulp) but yields ΔAUC = +0.013
  due to `roc_auc_score` argsort instability on a saturated dataset
  (73/120 eval clusters tied at p ≈ 1.0). Mechanism documented in
  `docs/phase-09/p91c_variance_diagnosis.md`.
- **[G-3.5b] identity-check override**: `scripts/refit_p91c.py` now uses a
  two-tier gate — PRIMARY `np.allclose(p_baseline, p_new, atol=1e-10)`
  for token re-fits, SECONDARY Brier/AUC thresholds (0.005 / 0.01) for
  real re-fits (P9.1e onwards). Re-run PASS via PRIMARY identity check;
  `models/scoring_v1_20260526_p91c.pkl` persisted as non-regression
  artifact.

## 2. Scope NOT delivered (explicit non-goals)

- **Scoring with real signal gain.** P9.1c was a *data-hygiene + trading*
  enablement sprint, not a model-improvement one. The [G] re-fit is a
  token non-regression record. Real signal-improving training waits on:
  - P9.1e (populate `premium_pct` for the 222 labelled clusters → revives
    the dead `bid_premium_pct` feature).
- **AMF / Consob parser offer_price.** 0 / 730 FR deals carry an
  `offer_price`; 5 / 47 IT do not. P9.1c only ported the structured
  extraction to the BaFin parser. The analogous fix for AMF / Consob,
  plus ISIN extraction, lives in **P9.2**.
- **`premium_pct` population.** No parser populates this column today;
  documented in `docs/scoring/known_issues.md` since P9.1b. Computing it
  requires `target_close` at `announcement_date - 1bd` for the 222
  labelled clusters via yfinance — exact dependency now ready (yfinance
  fetcher + target resolver), to be wired in **P9.1e**.

## 3. Measured impact

### Phase 8 trading
- **Commerzbank** (id 348) and **ProSieben** (id 1059) now carry
  `offer_price_total_eur` (31.07 € and 5.64 € respectively) and
  `pricing_source = 'yfinance_enriched'`. The Phase-8 `load_candidates`
  flow that filters on `verified_*` flags now exposes these 2 mixed
  deals as tradable (was: ineligible with the previous `suspect_mixed`
  flag + NULL total).
- Quality-flag distribution post-sprint on the BaFin labelled set:
  31 `verified_cash` + 1 `verified_mixed` (ProSieben; Commerzbank live)
  + 9 `manual_review` + 0 `suspect_*`. Clean for downstream consumption.

### Phase 6 scoring
- **Non-regression empirically verified.** Predictions byte-equivalent to
  baseline within 8 × 10⁻¹⁵ (`max|p_new - p_baseline|`), Brier and
  log_loss bit-identical. The AUC drift of +0.013 between baseline and
  refits is a rank-tie-breaking artifact on the saturated eval set
  (73/120 clusters at p ≈ 1.0), not a model behaviour change.

### Data hygiene
- 42 / 42 BaFin labelled deals at `parser_version = 2` (was 17/42).
- 9 manual_review DE labelled deals correctly excluded from the test
  slice for any future re-fit (`data/audits/p91c_train_test_split.csv`
  records the per-deal split).
- 0 outstanding `suspect_low_unverified` flags on labelled deals.

## 4. Re-fit metrology — the [G-3.5] finding

The [G] brief specified |dBrier| > 0.005 OR |dAUC| > 0.01 as the
non-regression breach threshold. The May-26 refit triggered the AUC
guard despite predictions identical to baseline at 1e-14 precision.

**Root cause:** `roc_auc_score` uses `argsort`, which is unstable on
ties. With 73 / 120 eval clusters saturated at p ≈ 1.0, an 8e-15 BLAS
/ OpenMP reduction noise from a cross-process refit reorders tied
predictions on the ROC saturated segment and shifts AUC by ~0.013.
Brier, log_loss, accuracy, F1 are not rank-based and stay bit-identical.

**Resolution:** added a PRIMARY identity check
(`np.allclose(p_baseline, p_new, atol=1e-10, rtol=0)`) ahead of the
threshold guard. Token re-fits pass on the identity gate; the 0.01 AUC
threshold remains armed for real re-fits where features actually change
(predictions will then move by ≫ 1e-10 and the threshold path will fire
with full strictness).

The `data/audits/p91c_refit_metrics.csv` gains a `check_used` column
(`identity` | `thresholds`) so the audit trail records which gate
validated each run.

## 5. Residual debt (open work)

### P9.1e — premium_pct + scoring V1.1 (next branch)
- **Goal:** populate `premium_pct` on the 222 labelled clusters, revive
  the dead `bid_premium_pct` feature, re-fit with real signal change.
- **Dependencies:** yfinance fetcher (delivered in [C]) + target ticker
  resolver (delivered in [E]) + announcement_date column (already
  populated).
- **Suggested branch:** `phase-09e-premium-pct-revival`.
- **Acceptance:** ≥ 80 % of labelled clusters with non-null
  `premium_pct`; re-fit triggers PRIMARY check FAIL (predictions
  diverged) but SECONDARY threshold PASS; AUC change documented and
  interpreted.

### P9.2 — AMF / Consob parser hardening
- **Goal:** port the BaFin structured-extraction pattern to AMF (BDIF)
  and Consob parsers. Extract `offer_price` (currently 0/730 FR,
  partial IT) and ISIN.
- **Suggested branch:** `phase-09-02-amf-consob-extraction`.
- **Acceptance:** FR / IT labelled clusters with `offer_price IS NOT
  NULL` ≥ 90 %; `offer_price_quality_flag` populated by parser verdict
  on FR + IT (no more migration default on FR / IT labelled).

### Smaller items
- `Deal.status = 'announced'` is not refreshed when `completion_label`
  is applied via the external labelling process (observed on 29 DE
  closed deals). Schedule a back-population utility for P10 (backtest)
  hygiene.
- The `MEN.F` rejected mapping should be revisited if a non-penny
  alternate listing emerges for the relevant target.

## 6. Artifact inventory

### Schema + data
- `alembic/versions/20260525_1500_0015_phase_09c_deal_consideration_pricing.py`
- 2 rows in `deal_consideration` (Commerzbank, ProSieben).
- 30 BaFin labelled deals with `pricing_source = 'parser_only' |
  'yfinance_enriched'`; the 12 unlabelled-or-manual-review carry the
  appropriate flag combinations from [F] and P9.1c-bis.

### Code
- `src/pricing/{yfinance_fetcher,acquirer_registry,target_ticker_resolver,recalc}.py`
- `src/ingestion/bafin/parser.py` (gained `_extract_consideration()` +
  `ConsiderationStructured`)
- 13 scripts under `scripts/` (probe / populate / recalc / validate /
  reparse / audit / variance / refit).

### Models
- `models/scoring_v1_20260520T141111Z.pkl` — baseline, unchanged.
- `models/scoring_v1_20260526_p91c.pkl` — non-regression artifact.

### Docs
- `docs/phase-09/p91c_*.md` (this file + 4 siblings:
  small_caps_validation, sanity_check, variance_diagnosis,
  scoring_features_audit) + `p91cbis_reparse_results.md`.

### Audits (gitignored under `data/audits/`)
- `p91c_offer_price_audit.csv`, `p91a_backfill_results.csv`,
  `p91c_small_cap_ticker_probe.csv`, `p91c_small_caps_validation.csv`,
  `p91cbis_reparse_results.csv`, `p91c_scoring_features_audit.csv`,
  `p91c_sanity_verified_labelled.csv`, `p91c_refit_variance.csv`,
  `p91c_refit_metrics.csv`, `p91c_train_test_split.csv`.

## 7. Next step — [H] PR + CI

Out of [G-4] scope: per the [G] brief, operator merges the PR manually.
Branch `phase-09c-yfinance-enrichment` is at HEAD `e47f304`, ready for
review. CI must be green before merge; no auto-merge is configured.
