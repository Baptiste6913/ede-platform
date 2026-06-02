# Phase 11 — Closure: OpenFIGI ISIN→ticker resolver + premium_pct backfill

## Executive summary (honest)

**Objective.** Replace the Phase-10 yfinance bare-ISIN resolver — which produced
wrong-security false positives (CLASQUIN +10405 %, COVIVIO −77 %) that would
silently poison an ML backfill — with OpenFIGI (Bloomberg's free, no-KYC mapping
service), and use it to populate `premium_pct` for the labelled set.

**Infrastructure result: SUCCESS.** OpenFIGI resolves an ISIN to the *correct
issuer* on main-market venues; combined with a premium sanity gate, the pipeline
emits **0 garbage** into the training set. The Phase-10 failure mode is closed.

**Volume result: PARTIAL.** Only **39 / 222 labelled deals (17.6 %)** ended up
with a usable `premium_pct`. The pipeline is *safe* but *coverage-limited* — the
gap is concentrated in three unresolved classes (Euronext Growth 72, data-gaps
50, no_match 13), none of which is a safety regression.

| | Phase 10 (yfinance) | Phase 11 (OpenFIGI) |
|---|---|---|
| Wrong-security FPs (identity) | 2 (silent) | **0** (gate-caught residuals → NULL) |
| Usable premium_pct | ~25 % real, garbage-contaminated | **39 deals, clean** |
| Pipeline safety | none | identity + premium gate |

## Methodology (Step 0–3)

- **Step 0 — pre-flight.** 3 sample ISINs (Mediobanca/Sanofi/SAP) confirmed
  OpenFIGI resolves the right issuer; corrected the brief's assumption that
  exchCode hints are MIC codes — OpenFIGI uses **Bloomberg** codes (FP/IM/GR/GY;
  XPAR/MTAA return "No identifier found").
- **Step 1 — resolver.** `OpenFIGIResolver`: `resolve_isin` (equity rows only) →
  `select_home_venue` (ISIN-country → Bloomberg exchCode, dominant-compositeFIGI
  fallback) → `bbg_to_yahoo_suffix`. Disk cache, 25 req/min throttle, 28 tests.
- **Step 2 — sample (20 deals, mirror of P10).** 0 wrong-ticker FPs vs 2;
  resolution 10/17. Surfaced the FR Euronext Growth gap.
- **Step 2.5/2.6 — Growth mapping.** Added XS/XH/EO → .PA + currency-suffix
  strip; resolution rose to 17/17. **But a yfinance identity spot-check showed
  Bloomberg's Growth ticker ≠ the Yahoo symbol**: `ALCLAEUR`→`ALCLA.PA` is
  *Claranova*, not Clasquin. Flagged these `home_venue_growth` (low confidence).
- **Step 3 — migration 0016 + full backfill** of the 187 labelled+ISIN deals.

## Key win

**0 wrong-security false positives at the identity layer** (vs 2 in Phase 10).
Every main-market (`home_venue`) resolution that priced and passed the gate is
the correct security. OpenFIGI's compositeFIGI/shareClassFIGI structure makes
"is this the right company?" reliably answerable.

## Cross-cutting finding: BBG ticker ≠ Yahoo symbol — the gate is NOT optional

The Bloomberg local ticker OpenFIGI returns is not always the Yahoo symbol, and
the mismatch is **not limited to Euronext Growth**:

- `ALCLAEUR`→`ALCLA.PA` = Claranova (Growth, low-confidence).
- **`Turbon AG` (DE0007504508) → `TUR.DE` = iShares MSCI Turkey ETF** (main-market
  Xetra GR; ref 39.09 EUR vs Turbon ~3 EUR → −91 %).
- `CompuGroup` (DE000A288904) → `COP.DE` has **0 rows on yfinance** (5y) — the
  Yahoo symbol differs.

The **premium sanity gate** ([−50 %, +200 %]) caught the wrong-security residuals
and left their `premium_pct` NULL. Conclusion: pipeline safety = **OpenFIGI
identity + premium gate together**, not either alone.

## Results

**Distribution by `ticker_resolution_flag` (187 processed):**

| flag | N | meaning |
|---|---:|---|
| `home_venue` | 46 | main-market priced (39 with premium, 7 no offer_price) |
| `home_venue_growth` | 72 | Euronext Growth — routed to manual_review (unsafe heuristic) |
| `no_price_data` | 36 | resolved but no Yahoo data (delisting / BBG≠Yahoo symbol) |
| `unknown_exch` | 14 | venue not in the suffix table |
| `no_match` | 13 | OpenFIGI returns no equity row |
| `premium_out_of_bounds` | 6 | gate-caught → `premium_pct` NULL |

**`premium_pct` distribution (39 gate-passed, %):** mean 2.65 · median 1.30 ·
stdev 11.26 · range −25.00 → +32.67. Lower than the textbook 10–35 % M&A-arb
premium because the T-1 reference often already reflects the bid (leaks,
second-step / squeeze-out offers priced near the prevailing quote).

## Honest assessment

39 usable observations is a **sparse** feature. A V2 retrain on it will be
imputation-dominated (≈ 83 % of the labelled set still NaN on premium_pct), so
the marginal AUC lift over V1 may be small. Phase 11 delivered the *safe
infrastructure* to compute the feature; it did not deliver the *volume* needed
to make the feature decisive. That is the accurate state.

## Tech debt (Phase 12+)

1. **offer_price parsing** — corrupt values surfaced by the gate: COVIVIO 3.00 EUR
   (vs ~13), VOGO +556 %, ALBA SE −87 %. Upstream data-quality fix.
2. **no_price_data recovery** — high-value deals resolvable with the correct
   Yahoo symbol (CompuGroup ×2: COP.DE → find the real Yahoo ticker).
3. **Euronext Growth strategy (72 deals)** — replace the currency-strip heuristic
   with a safe path: cross-check `yf …info.shortName` vs `target_name`, or a
   curated ISIN→Euronext-mnemonic map.
4. **unknown_exch venue mapping (14 deals)** — extend `BBG_TO_YAHOO_SUFFIX`.
5. **IT/Consob ISIN extraction** — no ISIN means OpenFIGI cannot run; blocks all
   IT deals upstream (mirror the FR PDF extraction onto Consob).

## Phase 12 decision (to debate)

- **Option A — retrain V2 now** on the 39 premium deals + imputation. Tests the
  hypothesis cheaply; accept a possibly-marginal result.
- **Option B — widen coverage first** (Growth curation + offer_price fix + a few
  no_price_data recoveries) to reach ~80–100 premium deals before V2, so the
  feature has a fair chance of mattering.

Recommendation: **B if the V2 lift matters; A as a fast falsification test.** The
safe pipeline (this phase) makes either path low-risk — neither can poison the
model.

## Commits

| Step | Commit | Summary |
|---|---|---|
| 0 | `d73aadb` | OpenFIGI pre-flight on 3 sample ISINs |
| 1 | `2914785` | resolver + Bloomberg→Yahoo venue mapping (28 tests) |
| 2 | `9e2db10` | sample test 20 deals — 0 FP, resolution 10/17 |
| 2.5 | `55f0646` | Euronext Growth mapping + currency strip (home_venue_growth) |
| 2.6 | `82c8fc0` | re-run + Growth safety finding (ALCLA.PA→Claranova) |
| 3 | `ec15c15` | migration 0016 + full backfill — 39 usable premium_pct |
