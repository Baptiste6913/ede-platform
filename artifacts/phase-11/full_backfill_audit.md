# Phase 11 Step 3 — full premium_pct backfill (OpenFIGI home_venue)

Processed **187** deals this run (resume-skipped 0 already-flagged). Auto-backfill restricted to main-market resolutions (home_venue / venue_fallback) with the premium sanity gate enforced; home_venue_growth routed to manual_review.

## Distribution by flag

| ticker_resolution_flag | Count |
|---|---:|
| `home_venue` | 46 |
| `home_venue_growth` | 72 |
| `no_match` | 13 |
| `no_price_data` | 36 |
| `premium_out_of_bounds` | 6 |
| `unknown_exch` | 14 |
| **TOTAL processed** | **187** |

## Coverage

- Deals with a usable `premium_pct` (gate-passed): **39**.
- Deals priced (home_venue/venue_fallback reached pricing): 46.
- Labelled deals total (incl. IT no-ISIN, not in this run): 222.

## premium_pct distribution (gate-passed, shown as %)

- count : 39
- mean  : 2.65 %
- median: 1.30 %
- min   : -25.00 %
- max   : 32.67 %
- stdev : 11.26 %

## Outliers gate-caught (premium_out_of_bounds)

| Ref | Target | ISIN | Ticker | premium % | likely cause |
|---|---|---|---|---:|---|
| 224C0763 | COVIVIO HOTELS | FR0000060303 | COVH.PA | -77.16 | wrong-ticker or corrupt offer_price |
| BAFIN-DE0006209901-20241028 | ALBA SE | DE0006209901 | ABA.DE | -87.00 | wrong-ticker or corrupt offer_price |
| 225C1794 | VOGO | FR0011532225 | ALVGO.PA | 556.00 | wrong-ticker or corrupt offer_price |
| BAFIN-DE0007504508-20251021 | Turbon AG | DE0007504508 | TUR.DE | -91.46 | wrong-ticker or corrupt offer_price |
| 225C1258 | VOGO | FR0011532225 | ALVGO.PA | 556.00 | wrong-ticker or corrupt offer_price |
| 225C1139 | ELECTRICITE ET EAUX DE | FR0000035719 | EEM.PA | -57.39 | wrong-ticker or corrupt offer_price |

## manual_review queue (growth + no_match + unknown_exch + not_isin)

- 99 deals flagged for manual review (excluded from auto-backfill).
