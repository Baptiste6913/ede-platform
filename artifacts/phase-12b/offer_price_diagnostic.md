# P12b — offer_price diagnostic (gate-caught deals)

The Phase-11 premium gate flagged 6 deals `premium_out_of_bounds`. An identity
cross-check (yfinance shortName vs target_name) + a DB pricing dump
(`offer_price`, `offer_price_total_eur`, `deal_consideration`) classifies each as
**corrupt offer** (ticker+reference correct, offer wrong → recoverable) vs
**wrong reference** (ticker resolves to the wrong security → not an offer bug).

## Classification

| Ref | Target | Ticker | yfinance identity | ref EUR | offer | premium | Class |
|---|---|---|---|---:|---:|---:|---|
| 224C0763 | COVIVIO HOTELS | COVH.PA | ✅ COVIVIO HOTELS | 13.14 | 3.00 | −77 % | **corrupt offer** |
| 225C1258 | VOGO | ALVGO.PA | ✅ VOGO | 2.50 | 16.40 | +556 % | **corrupt offer** |
| 225C1794 | VOGO | ALVGO.PA | ✅ VOGO | 2.50 | 16.40 | +556 % | **corrupt offer** |
| 225C1139 | ELECTRICITE ET EAUX | EEM.PA | ✅ Élec. & Eaux Madagascar | 3.52 | 1.50 | −57 % | borderline (verify) |
| DE…0006209901 | ALBA SE | ABA.DE | ❌ `"ABA.DE,0P00009R3L,0"` (a fund) | 61.10 | 7.94 | −87 % | **wrong reference** |
| DE…0007504508 | Turbon AG | TUR.DE | ❌ Lyxor MSCI Turkey UCITS ETF | 39.09 | 3.34 | −87 % | **wrong reference** |

## Findings

- **`offer_price_total_eur` is NULL and `deal_consideration` is empty for all 6**
  (`pricing_source = parser_only`). There is **no alternative correct offer value
  in the DB** — fixing a corrupt offer requires re-parsing the source PDF or
  external verification. No value is fabricated here.
- **2 of the 6 are wrong references, not offer bugs** (ALBA SE → ABA.DE resolves
  to a fund; Turbon → TUR.DE = the iShares/Lyxor Turkey ETF). These are the same
  BBG-ticker ≠ Yahoo-symbol collision class seen at Growth level (ALCLA→Claranova)
  — but at **main-market** (Xetra GR). The premium gate caught both; the
  resolved tickers are wrong and (Turbon/ALBA being effectively delisted) have no
  valid yfinance series. Not recoverable via an offer fix.
- **Recoverable via offer re-parse: COVIVIO (1) + VOGO (2 deals = 1 cluster)** →
  ~2 clusters, *only if* the true offer is recovered from the PDF. Offer 3.00 for
  a 13 EUR stock and 16.40 for a 2.50 EUR stock are clear parser artifacts.
- ELECTRICITE ET EAUX is borderline: ticker correct, but a −57 % offer could be a
  genuine below-market squeeze-out on an illiquid holding. Needs PDF check.

## Implication

The offer_price gisement yields **~2 recoverable clusters** and requires per-deal
PDF re-parsing (no DB shortcut). Combined with Growth's +3, coverage expansion
tops out around **~30 clusters** — far from the 80–100 Option-B target. The
binding constraints are (a) yfinance not covering delisted EU small caps and
(b) offer_price parser quality. Both are Phase-13 workstreams.

## Phase 13 actions (deferred, not done here)

1. **offer_price re-parse** for COVIVIO 224C0763 + VOGO 225C1258/225C1794 (clear
   corrupt scalars) → recover ~2 clean premium clusters.
2. **Resolver identity cross-check** wired into the backfill so main-market
   wrong-references (Turbon→TUR.DE, ALBA→ABA.DE) are rejected at resolution time,
   not only by the premium gate (defense in depth).
3. **Alternative price source** for delisted EU small caps (the 24 no_data Growth
   clusters + Turbon/ALBA) — the only path to materially densify premium_pct.
