# P9.1c-[F] — small-cap DE offer_price validation

External cross-check (yfinance EOD) of the 12 BaFin small-cap deals
(`offer_price < 5 EUR` per the Step-0 audit, currently `verified_cash` after
P9.1a). For each deal: resolve the target Yahoo ticker via
`target_ticker_resolver`, fetch the close at `announcement_date - 1` business
day, compute deviation vs `offer_price`. Threshold: 30%.

## Ticker probe — 5 / 11 ISIN resolved

`scripts/probe_small_cap_tickers.py` → `data/audits/p91c_small_cap_ticker_probe.csv`.

| outcome | count | tickers |
|---|--:|---|
| OK (added to registry) | 3 | ALG.DE, KA8.DE, CEC.DE |
| OK but rejected (false-positive map) | 2 | TUR.DE (iShares Turkey ETF), MEN.F (penny stock) |
| MISS (delisted post-OPA) | 6 | LEO, SPM, READ, DFV, WCMK, FPH |

The two false positives are kept in `REJECTED_TICKER_MAPPINGS` as an
anti-regression memo so a future operator doesn't re-attempt them.

## Validation outcome — 3 verified, 9 manual_review

| deal | target | offer | close T-1bd | dev | new_flag |
|--:|---|--:|--:|--:|---|
| 1071 | Klassik Radio | 3.70 | 3.6225 | **2.14%** | `verified_cash` ✅ |
| 353 | CECONOMY | 4.60 | 4.45 | **3.37%** | `verified_cash` ✅ |
| 1077 | Albis Leasing | 2.80 | 2.6144 | **7.10%** | `verified_cash` ✅ |
| 351 | Turbon | 3.34 | — | — | `manual_review` (rejected ticker) |
| 1068 | MedNation | 1.50 | — | — | `manual_review` (rejected ticker) |
| 352, 355, 356, 358, 1073, 1074, 1078 | (7 delisted) | various | — | — | `manual_review` (ticker_unresolved) |

**Three verified_cash double-sourced** (deviation < 10% on each) — the P9.1a
parser's verdict is independently confirmed by external yfinance data on these.

**Nine manual_review** are NOT a parser failure but a *coverage limitation*:
small-cap targets that complete an OPA (Erwerbsangebot) typically get
squeezed out and delisted from Xetra/Frankfurt; yfinance therefore has no
post-OPA history. Expected and well-handled by the threshold + dry-run flow.

### Note on DFV (deal 1078, 6.60 EUR)
DFV was corrected from 2.00 → 6.60 EUR in the P9.1a backfill (par-value
misparse — see `p91a_fix_summary.md` and `p91a_backfill_results.csv`). The
6.60 EUR is the parser's anchored extraction from the PDF (Geldleistung clause)
and was approved at the P9.1a checkpoint. The yfinance ticker (DFV.DE/F) is
delisted post-OPA, so the [F] validation routes DFV to `manual_review` —
*not* because the parser is wrong, but because there is no external feed left
to confirm it. The 6.60 EUR remains the best available value; manual_review
flags it as "parser-only, no external confirmation possible".

## DB state post-apply

| flag | DE count | composition |
|---|--:|---|
| `verified_cash` | 6 | 3 confirmed at [F] + 3 untouched (Linus, infas, Philomaxcap) |
| `verified_mixed` | 2 | Commerzbank, ProSieben (P9.1c-[E] recalc) |
| `manual_review` | 9 | This checkpoint's downgrades |
| `suspect_low_unverified` | 25 | Non-outlier deals, never re-parsed |
| **total** | **42** | |

## Take-aways for [G] (re-scoring) and Phase 10 (backtest)

- The 9 manual_review deals **must be excluded** from training datasets — no
  external confirmation, parser-only. They can be revisited via manual review
  (Boerse Frankfurt archives, financial press) but that's out of V1 scope.
- The structurally-poor yfinance coverage on post-OPA delistings means the
  tradable DE universe is smaller than the headline count of 42 deals.
  P9.2 (ISIN extraction for FR / IT, ~200 deals) is the higher-leverage path
  to a usable backtest, not deeper investigation of the German small-caps.
- The threshold 30% behaved exactly as intended: 0 false-negative
  (no aberrant offer escaped flagging), 2 false-positive ticker maps caught
  early. A reviewer-confirmed `verified_cash` from this run is genuinely
  double-sourced.
