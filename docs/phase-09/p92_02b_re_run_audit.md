# Phase 9.2 02b — Step 1h re-run audit

Re-runs the post-fix AMF parser (`src/ingestion/amf/parser.py`, Steps 1b + 1c) on every FR `verified_cash` deal and compares the extracted price with the value currently stored in the DB. **No DB write** — this is the validation checkpoint before Step 1i applies the corrections.

## 1. Summary

- Deals re-parsed: **596**

| Category | Count | Share |
|---|---:|---:|
| `UNCHANGED` | 532 | 89.3% |
| `CORRECTED` | 64 | 10.7% |
| `NEW_DIFFERENT` | 0 | 0.0% |
| `PARSER_FAIL` | 0 | 0.0% |
| `NEW_EXTRACT` | 0 | 0.0% |

### Correction provenance

| Source label | Count |
|---|---:|
| `engagement_clause` | 62 |
| `surenchere_raised` | 2 |

### Correction delta (|new - old| / old, %)

- count : 64
- min   : 0.25
- median: 10.19
- max   : 16200.00

## 2. Top 20 corrections (by |delta %|)

| Ref | Target | Old | New | Δ % | Source |
|---|---|---:|---:|---:|---|
| 223C2035 | TECHNICOLOR CREATIVE STUDIOS | 0.010000 | 1.63 | 16200.00 | `engagement_clause` |
| 220C4301 | ANTALIS | 0.100000 | 0.90 | 800.00 | `engagement_clause` |
| 220C2611 | ANTALIS | 0.100000 | 0.73 | 630.00 | `engagement_clause` |
| 219C2667 | OENEO | 2.720000 | 13.50 | 396.32 | `engagement_clause` |
| 224C1143 | ADEUNIS | 0.175000 | 0.45 | 157.14 | `engagement_clause` |
| 224C0888 | ADEUNIS | 0.175000 | 0.45 | 157.14 | `engagement_clause` |
| 221C2876 | IVALIS | 11.450000 | 24.50 | 113.97 | `engagement_clause` |
| 221C2321 | IVALIS | 11.450000 | 24.50 | 113.97 | `engagement_clause` |
| 217C2901 | FONCIERE DEVELOPPEMENT LOGEMENTS-FDL | 4.210000 | 8.06 | 91.45 | `engagement_clause` |
| 217C2716 | FONCIERE DEVELOPPEMENT LOGEMENTS-FDL | 4.210000 | 8.06 | 91.45 | `engagement_clause` |
| 218C0690 | A2MICILE EUROPE | 27.000000 | 45.30 | 67.78 | `engagement_clause` |
| 218C0608 | A2MICILE EUROPE | 27.000000 | 45.30 | 67.78 | `engagement_clause` |
| 224C1700 | GALIMMO | 9.020000 | 14.83 | 64.41 | `engagement_clause` |
| 224C1562 | GALIMMO | 9.020000 | 14.83 | 64.41 | `engagement_clause` |
| 225C1227 | GROUPE ETPO SA | 61.000000 | 82.33 | 34.97 | `engagement_clause` |
| 225C0838 | GROUPE ETPO SA | 61.000000 | 82.33 | 34.97 | `engagement_clause` |
| 217C0730 | EURO DISNEY S.C.A. | 3.000000 | 2.00 | -33.33 | `engagement_clause` |
| 224C1289 | TRAVEL TECHNOLOGY INTERACTIVE | 2.340000 | 2.85 | 21.79 | `engagement_clause` |
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.340000 | 2.85 | 21.79 | `engagement_clause` |
| 218C1043 | CFI-COMPAGNIE FONCIERE INTERNATIONALE | 0.830000 | 1.00 | 20.48 | `engagement_clause` |

## 3. NEW_DIFFERENT cases (low-confidence new value — review)

_None._

## 4. PARSER_FAIL cases (new logic returns None)

_None._

## 5. NEW_EXTRACT cases (parser now finds where old missed)

_None — expected, since the input set is verified_cash (every row had a stored price)._

## 6. Recommendation

**Proceed to Step 1i.** Every change is a CORRECTED row with a high-confidence source label. The DB update can safely apply the `new_offer_price` column to the `CORRECTED` rows transactionally.


_Raw audit CSV: `data/audits/p92_02b_re_run_comparison.csv` (gitignored, 596 rows)._