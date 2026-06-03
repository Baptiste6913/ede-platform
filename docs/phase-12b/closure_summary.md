# Phase 12b — Closure: premium_pct coverage expansion (data-limited)

## Objective

Phase 12 Step A confirmed a sparse premium_pct signal (coef −0.67, 25 clusters).
Option B aimed to widen coverage to ~80–100 clusters — for a stable coefficient
and a genuine out-of-sample CV AUC — via two gisements: (1) Euronext Growth
identity recovery, (2) corrupt offer_price fixes.

## Result — both gisements are data-limited; target unreachable

**The ~80–100 target is not reachable from these sources.** Realistic ceiling
≈ **30 clusters** (25 current + ~3 Growth + ~2 offer-fix).

### Growth identity cross-check (Step 0) — +3, not worth wiring

A yfinance-name vs target_name cross-check (difflib, no new dep) cleanly
**confirms** correct tickers (BALYO.PA→"BALYO", ratio 1.00) and **rejects**
collisions (ALCLA.PA = Claranova). Method works. But over all 72
`home_venue_growth` deals → **28 clusters**:

| Verdict | Clusters |
|---|---:|
| ✅ CONFIRM (recoverable) | **3** |
| ❌ REJECT (collision, correctly excluded) | 1 |
| · no_data (delisted, no yfinance series) | 24 |

The bottleneck is **data availability, not identity**: 24/28 are delisted
micro-caps yfinance does not cover. Manual ISIN→mnemonic curation would not fix
them either (no price regardless of correct ticker). +3 clusters does not justify
wiring the cross-check into production.

### offer_price diagnostic (Step 2) — ~2 recoverable, needs PDF re-parse

Of the 6 gate-caught `premium_out_of_bounds` deals (see
`artifacts/phase-12b/offer_price_diagnostic.md`):
- **2 wrong references** (Turbon→TUR.DE = Turkey ETF; ALBA→ABA.DE = a fund) —
  the main-market analogue of the Growth collision; correctly gate-caught, not
  offer bugs, un-recoverable (delisted).
- **~2 corrupt offers** (COVIVIO 3.00 vs 13 EUR; VOGO 16.40 vs 2.50 EUR) —
  recoverable, but `offer_price_total_eur`/`deal_consideration` are NULL, so the
  true offer needs a PDF re-parse. No value fabricated.

## Decision (judgement call)

Coverage cannot be meaningfully expanded with yfinance + the current parser.
Therefore:
- **Growth production wiring: skipped** (+3 not worth the machinery).
- **offer_price re-parse: deferred to Phase 13** (manual per-deal PDF work for
  ~2 clusters; not fabricated here).
- **No V2 retrain at ~30 clusters** — it would not yield a trustworthy CV AUC,
  and Step A already answered the signal question. Retraining adds nothing.
- **V1 stays in prod.**

## Standing conclusion on premium_pct

The signal is **real but sparse** (Step A: coef −0.67, negative sign stable
3/3 folds) and **cannot be densified to "decisive" with current data sources**.
The binding blocker is **price-data coverage of delisted EU small/micro-caps**,
not ISIN resolution (Phase 11 solved that) nor feature wiring (already done).

## Phase 13 backlog (root-cause)

1. **Alternative price source** for delisted EU small caps — the only path to
   materially densify premium_pct (covers the 24 no_data Growth + Turbon/ALBA).
   Candidate: extract the pre-announcement reference price from the AMF/Consob/
   BaFin filings already parsed, or a paid data provider.
2. **offer_price parser hardening** + re-parse the 2 identified corrupt scalars
   (COVIVIO, VOGO).
3. **Resolver identity cross-check** in the backfill (reject main-market
   wrong-references like Turbon/ALBA at resolution time — defense in depth on top
   of the premium gate).
4. IT/Consob ISIN extraction (unchanged from Phase 11).

## Artifacts

- `artifacts/phase-12b/growth_crosscheck_preflight.md` — 28-cluster Growth inventory.
- `artifacts/phase-12b/offer_price_diagnostic.md` — 6 gate-caught deals classified.
- `scripts/p12b_growth_crosscheck_preflight.py` — reproducible cross-check.

## Commits

| Step | Commit | Summary |
|---|---|---|
| 0 | `ef5100e` | Growth cross-check pre-flight (sample) |
| 0 (full) | `278d84f` | Growth cross-check full inventory — 3/28 recoverable |
| closure | _this_ | coverage data-limited, V1 stays, Phase 13 backlog |
