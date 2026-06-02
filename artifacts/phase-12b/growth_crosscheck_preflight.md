# P12b Step 0 — Euronext Growth identity cross-check (FULL inventory)

All 72 `home_venue_growth` deals → **28 distinct (target, jurisdiction) clusters** (premium is per cluster). Cross-check = fuzzy-match the candidate Yahoo ticker's yfinance company name vs `target_name` (difflib token-sort ratio + distinctive-token, threshold >= 0.6 OR token hit). CONFIRM = identity matches; REJECT = collision (e.g. ALCLA.PA=Claranova); no_data = yfinance has no name (delisted micro-cap, also un-priceable).

## Cluster verdicts

| Target | Jur | ticker | yfinance name | ratio | verdict |
|---|---|---|---|---:|:--:|
| BALYO | FR | BALYO.PA | BALYO | 1.00 | ✅ CONFIRM |
| COMPAGNIE DU CAMBODGE | FR | CBDG.PA | CAMBODGE NOM. | 0.62 | ✅ CONFIRM |
| ESKER | FR | ESK.PA | Esker SA | 1.00 | ✅ CONFIRM |
| CLASQUIN | FR | ALCLA.PA | CLARANOVA | 0.47 | ❌ REJECT |
| AMPLITUDE SURGICAL | FR | AMPLI.PA | — | 0.00 | · no_data |
| AURES TECHNOLOGIES | FR | AURS.PA | — | 0.00 | · no_data |
| ETABLISSEMENTS FAUVET GI | FR | FAUV.PA | — | 0.00 | · no_data |
| FINANCIERE MONCEY | FR | MONC.PA | — | 0.00 | · no_data |
| FUTUREN | FR | TEOT1.PA | — | 0.00 | · no_data |
| GALIMMO | FR | CIEM.PA | — | 0.00 | · no_data |
| GROUPE PAROT | FR | ALPAR.PA | — | 0.00 | · no_data |
| IDSUD | FR | ALIDS.PA | — | 0.00 | · no_data |
| LE BELIER | FR | BELI.PA | — | 0.00 | · no_data |
| M2I | FR | MLMII.PA | — | 0.00 | · no_data |
| MICROPOLE | FR | MUN.PA | — | 0.00 | · no_data |
| MONTAGNE ET NEIGE DEVELO | FR | MND1.PA | — | 0.00 | · no_data |
| NHOA | FR | EPS1.PA | — | 0.00 | · no_data |
| ORAPI | FR | ORAP.PA | — | 0.00 | · no_data |
| PRODWARE | FR | ALPRO.PA | — | 0.00 | · no_data |
| SOMFY SA | FR | SO.PA | — | 0.00 | · no_data |
| SQLI | FR | SQI1.PA | — | 0.00 | · no_data |
| TARKETT S.A. | FR | TKTT.PA | — | 0.00 | · no_data |
| TIPIAK | FR | TIPI.PA | — | 0.00 | · no_data |
| TRAVEL TECHNOLOGY INTERA | FR | ALTTI.PA | — | 0.00 | · no_data |
| TRONIC'S MICROSYSTEMS S. | FR | ALTRO.PA | — | 0.00 | · no_data |
| UNION FINANCIERE DE FRAN | FR | UFF.PA | — | 0.00 | · no_data |
| VERALLIA | FR | ALVIV.PA | — | 0.00 | · no_data |
| WEDIA | FR | ALWED.PA | — | 0.00 | · no_data |

## Counts (cluster level)

- Distinct Growth clusters: **28**
- ✅ CONFIRM (identity matches, recoverable): **3**
- ❌ REJECT (collision, correctly excluded): 1
- · no_data (delisted, un-priceable regardless): 24
- · no_ticker: 0

**Note:** CONFIRM is the *identity* ceiling. Usable premium also needs a T-1 yfinance price + passing the premium gate — a further haircut on the 3 confirmed.

## Go/no-go

- **Thin (3 confirmed clusters).** Growth recovery is data-limited (no_data dominates); the ~80-100 target is not reachable from Growth. Re-scope: offer_price fixes only, or accept the ceiling.
