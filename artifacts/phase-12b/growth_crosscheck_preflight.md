# P12b Step 0 — Euronext Growth identity cross-check pre-flight

72 deals flagged `home_venue_growth`. Cross-check = fuzzy-match the candidate Yahoo ticker's company name (yfinance shortName/longName) against `target_name`; CONFIRM on match, REJECT collisions (ALCLA.PA=Claranova). difflib token-sort ratio + distinctive-token containment (token >=5 chars present), threshold ratio >= 0.6 OR hit.

## Sample (10 deals)

| Deal | target_name | ticker | yfinance name | ratio | tok-hit | verdict |
|---|---|---|---|---:|:--:|:--:|
| 12 | BALYO | BALYO.PA | BALYO | 1.00 | Y | ✅ CONFIRM |
| 20 | BALYO | BALYO.PA | BALYO | 1.00 | Y | ✅ CONFIRM |
| 22 | PRODWARE | ALPRO.PA | — | 0.00 | n | · no-data |
| 26 | BALYO | BALYO.PA | BALYO | 1.00 | Y | ✅ CONFIRM |
| 29 | PRODWARE | ALPRO.PA | — | 0.00 | n | · no-data |
| 30 | TRONIC'S MICROSYSTEMS  | ALTRO.PA | — | 0.00 | n | · no-data |
| 31 | PRODWARE | ALPRO.PA | — | 0.00 | n | · no-data |
| 36 | TRONIC'S MICROSYSTEMS  | ALTRO.PA | — | 0.00 | n | · no-data |
| 37 | AMPLITUDE SURGICAL | AMPLI.PA | — | 0.00 | n | · no-data |
| 39 | TRONIC'S MICROSYSTEMS  | ALTRO.PA | — | 0.00 | n | · no-data |

## Estimate

- Sample CONFIRMED: **3/10** (30 %).
- Sample with a yfinance name (resolvable): 3/10.
- Projected over 72 Growth deals: **~22** recoverable.

## Go/no-go

- **<30 projected (~22)** — fuzzy cross-check alone is thin; manual ISIN→Euronext-mnemonic curation likely needed. Re-discuss.
