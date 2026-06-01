# Phase 10 — pre-flight findings

Inventory + sample mapping test before any code is written. The brief
underestimates one structural blocker on FR/IT — surfaced here so the
scope can be re-cut before Step 1 instead of after.

## 1. Pricing infra (existing, reusable)

| Module | Status | API |
|---|---|---|
| `src/pricing/yfinance_fetcher.py` | **mature** (P9.1c) | `get_close_eur(ticker, target_date, *, max_lookback_days=5) -> tuple[Decimal, date] \| None` — SQLite cache 30 d, FX EUR conversion, lookback to skip weekends/holidays, 4× retry with backoff |
| `src/pricing/target_ticker_resolver.py` | **partial** | `resolve_target_ticker(isin) -> str \| None` — static map, **5 DE ISINs only** (Commerzbank, ProSiebenSat.1, Albis Leasing, Klassik Radio, CECONOMY) |
| `src/pricing/acquirer_registry.py` | OK (P9.1c) | unrelated (acquirer-side, not target) |
| `src/pricing/recalc.py` | OK (P9.1c) | unrelated (mixed-offer total recompute) |

**stooq fetcher: does NOT exist** in the repo. Brief mentions a stooq
fallback; we'd have to build one from scratch. yfinance with a
weekend/holiday lookback already covers most of the brief's
"T-2 cover bank holidays" case, so stooq is not strictly required.

## 2. Schema state

```
alembic_version: 0015
```

| Column | Type | State |
|---|---|---|
| `deals.ticker_target` | `VARCHAR(32)` (indexed) | exists; populated **DE only** (35 / 39 labelled rows) |
| `deals.premium_pct` | `NUMERIC(7,4)` | exists; **NULL on every row** (222 labelled) |
| `deals.reference_price_at_announcement` | — | **does not exist** → migration 0016 needed |
| `deals.reference_price_source` | — | does not exist |
| `deals.reference_price_date` | — | does not exist |

## 3. Labelled-set composition

```
juridiction | labelled | with_ticker | with_premium
------------+----------+-------------+--------------
FR          |   148    |      0      |      0
IT          |    35    |      0      |      0
DE          |    39    |     35      |      0
            |  ----    |   ----      |   ----
            |   222    |     35      |      0
```

**Structural blocker** : 183 / 222 labelled deals (FR + IT) carry **no
ticker_target**. No ticker → no `get_close_eur(...)` call → no
reference_price → no premium_pct.

The DE-only path covers 35 / 222 = **15.8 %** of the training set.

## 4. Sample mapping test — 5 DE labelled deals (bare-ISIN passthrough)

Call chain: `resolve_target_ticker(isin) → fallback bare-ISIN →
get_close_eur(...)` at `announcement_date - 1 day`.

| Ref | Target | ISIN | Result |
|---|---|---|---|
| 350 | PSI Software SE | DE000A0Z1JH9 | **OK** — 44.30 € (eff_date 2025-11-14, weekend lookback) |
| 351 | Turbon AG | DE0007504508 | OK — 2.52 € **BUT** `REJECTED_TICKER_MAPPINGS` documents this as the iShares MSCI Turkey ETF, NOT Turbon AG → known false positive |
| 352 | Readcrest Capital AG | DE000A1E89S5 | **NO DATA** (yfinance: "Invalid ISIN") |
| 354 | Heidelberger Beteiligungsholding AG | DE000A254294 | **OK** — 105.0 € |
| 355 | Francotyp-Postalia Holding AG | DE000FPH9000 | **NO DATA** ($FPH.HM possibly delisted) |

Honest success rate: **2 / 5 = 40 %** (Turbon counts as a known false
positive, not a real hit). Without the `TARGET_TICKER_MAP` being
properly extended for DE, the bare-ISIN passthrough is too unreliable.

## 5. Sample mapping test — 5 FR labelled deals (ISIN extraction from PDF)

Tried to recover the missing FR ticker via a simple regex on the BDIF
PDFs (`\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b`):

| Ref | Target | ISIN extracted from page 1-3 |
|---|---|---|
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | `FR0010383877` |
| 219C2667 | OENEO | `FR0000052680` |
| 218C1907 | SERMA GROUP | `FR0000073728` |
| 224C1143 | ADEUNIS | `FR0013284627` |
| 223C2035 | TECHNICOLOR CREATIVE STUDIOS | `FR001400I939` |

**5 / 5 ISIN extracted, all unique, all FR-prefixed.** A ~1 h regex
sub-sprint on AMF + Consob PDFs would populate `ticker_target` on the
148 FR + 35 IT labelled rows — this is effectively the "P9.2 02c ISIN
extraction" already listed in the 02a closure summary as next sprint.

## 6. Cost of Phase 10 as scoped vs. reality

The brief assumed Phase 10 = `[reference_price fetcher + backfill +
wire + retrain]` in 4-6 h. The real critical path is:

1. **DE ticker map extension** (~30 min) — extend `TARGET_TICKER_MAP`
   with the ~30 DE ISINs not yet mapped, ideally via yfinance search
   + manual confirm + record `REJECTED_TICKER_MAPPINGS` for
   known-wrong ones. Otherwise the bare-ISIN passthrough has ~40 %
   success rate.
2. **Mini P9.2 02c — ISIN regex extraction** (~1.5 h) — extract ISIN
   from AMF + Consob PDFs, persist into `deals.ticker_target` for
   the 148 FR + 35 IT labelled rows.
3. **Migration 0016** (~30 min) — add `reference_price_at_announcement`
   + source + date columns.
4. **`get_close_eur` wrapper** (~30 min) — already exists. We need a
   thin `fetch_reference_price(deal)` that resolves ticker → close →
   stores into the new columns.
5. **Sample backfill (50 deals)** (~30 min) — measure success rate
   per jurisdiction. Stop checkpoint.
6. **Full backfill (222 labelled + 596 - 35 - 39 = 522 unlabelled
   verified_cash if we want the full corpus, or just 222 if we want
   labelled-only)** (~1-2 h depending on volume + yfinance rate
   limits).
7. **Wire `premium_pct` into features** (~30 min).
8. **Retrain V2 + audit** (~45 min).
9. **Closure + commit + push + PR** (~45 min).

**Total realistic: 6-8 h.** Beyond the 4-6 h budget, especially if we
add the mini P9.2 02c.

## 7. Options to validate before Step 1

### Option A — Phase 10 DE-only, honest framing (3-4 h, fits budget)

- Extend `TARGET_TICKER_MAP` with the missing DE ISINs (manual +
  yfinance search).
- Migration 0016 + reference_price fetcher wrapper.
- Backfill **39 DE labelled** deals only.
- Wire `premium_pct` into features.
- Retrain V2.
- Closure framing: "DE proof-of-concept; FR/IT requires P9.2 02c
  sprint, scoped in this closure".
- **Expected V2 impact: small.** 39 / 222 = 17.6 % of the training
  set gets the new feature. AUC delta likely in the 0.005-0.02 band,
  not the 0.04-0.10 hypothesised in the closure 02b §9 P10 tech debt.
- Honest about the limitation upfront.

### Option B — Full Phase 10 with mini-02c absorbed (6-8 h, over budget)

- Mini 02c: ISIN regex extraction on AMF + Consob → populate
  `ticker_target` for 183 FR + IT rows.
- DE ticker map extension.
- Migration 0016 + fetcher + sample test (extended to 20 deals, mix
  jurisdictions).
- Full backfill on 222 labelled (and optionally the 596 + 35 + 33
  verified_cash if we want maximum corpus).
- Wire + retrain + closure.
- **Expected V2 impact: full.** 222 / 222 enriched (modulo fetcher
  success rate per jurisdiction, currently ~40 % DE bare-ISIN,
  unknown FR/IT).

### Option C — Hybrid measure-then-decide (4-5 h, fits if we cut the corpus)

- Mini 02c ISIN extraction (1.5 h).
- DE ticker map extension (0.5 h).
- Sample test on 20 deals mix FR/IT/DE (0.5 h) → measure success rate.
  - **Go-criterion**: ≥ 70 % overall success rate on the sample.
  - **Fallback**: if FR or IT < 70 %, scope back to DE-only (Option A)
    and ship that. The mini-02c work is not wasted — it lands as
    P9.2 02c regardless.
- Migration + selected backfill + wire + retrain + closure.

### Recommendation

**Option C.** Measure before committing to the full corpus. The mini
02c work is independently valuable (P9.2 02c was already roadmapped),
so it lands either way. The DE-only fallback is honest if the FR/IT
fetcher success rate is too low.

## 8. Other decisions to validate

1. **stooq fallback** — brief mentions it. Repo doesn't have it.
   yfinance + business-day lookback covers most of the holiday case.
   Skip stooq for Phase 10; revisit if yfinance success rate is
   below 60 %.
2. **reference_price_date scope** — store `announcement_date - 1
   business day` as the *target* and the *effective* trading date
   returned by yfinance (they may differ on Mondays / holidays).
   Both stored separately in the new `reference_price_date` column,
   or in two columns `reference_price_target_date` +
   `reference_price_effective_date`. The cleaner version is two
   columns; minimal version is one column with the effective date
   only.
3. **Backfill scope** — labelled-only (222 deals) for the V2 retrain,
   OR full verified_cash corpus (596 FR + 35 IT + 33 DE = 664)? The
   training set only needs the 222; the full corpus is for downstream
   features / dashboard / future labelling. For Phase 10 strict scope
   = 222 labelled, with the script designed to extend to the full
   corpus in a Phase 10.5 sprint.

## 9. Next step — stop checkpoint

No code written. Branch `phase-10-premium-pct-wiring` created at
`134cc70` (main HEAD).

Awaiting user decision on:

1. Option **A / B / C** for the scope (recommend C).
2. stooq fallback — skip (yes/no).
3. reference_price_date — one column or two.
4. Backfill scope — labelled-only or full verified_cash.
