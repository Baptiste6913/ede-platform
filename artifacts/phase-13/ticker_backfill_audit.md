# Phase 13 — ticker backfill audit

Deals processed (ISIN, ticker not yet stored): **190**

## Persisted flag distribution

| flag | count |
|---|---:|
| `home_venue` | 49 |
| `home_venue_growth` | 72 |
| `no_match` | 13 |
| `no_price_data` | 36 |
| `premium_out_of_bounds` | 6 |
| `unknown_exch` | 14 |

## By jurisdiction x flag

| jurisdiction | flag | count |
|---|---|---:|
| DE | `home_venue` | 14 |
| DE | `no_match` | 1 |
| DE | `no_price_data` | 17 |
| DE | `premium_out_of_bounds` | 2 |
| DE | `unknown_exch` | 8 |
| FR | `home_venue` | 35 |
| FR | `home_venue_growth` | 72 |
| FR | `no_match` | 12 |
| FR | `no_price_data` | 19 |
| FR | `premium_out_of_bounds` | 4 |
| FR | `unknown_exch` | 6 |

## FR home_venue with clean ticker persisted — 35

| ISIN | yahoo (price) | ibkr_ticker | ibkr_exchange |
|---|---|---|---|
| FR0000033599 | ALLEX.PA | ALLEX | SBF |
| FR0000033599 | ALLEX.PA | ALLEX | SBF |
| FR0000035719 | EEM.PA | EEM | SBF |
| FR0000035719 | EEM.PA | EEM | SBF |
| FR0000039232 | AURE.PA | AURE | SBF |
| FR0000050353 | FII.PA | FII | SBF |
| FR0000053837 | LTA.PA | LTA | SBF |
| FR0000053837 | LTA.PA | LTA | SBF |
| FR0000053837 | LTA.PA | LTA | SBF |
| FR0000064404 | EDI.PA | EDI | SBF |
| FR0000064404 | EDI.PA | EDI | SBF |
| FR0000064404 | EDI.PA | EDI | SBF |
| FR0000064404 | EDI.PA | EDI | SBF |
| FR0000074197 | FPG.PA | FPG | SBF |
| FR0000074197 | FPG.PA | FPG | SBF |
| FR0000076952 | ARTO.PA | ARTO | SBF |
| FR0000076952 | ARTO.PA | ARTO | SBF |
| FR0000076952 | ARTO.PA | ARTO | SBF |
| FR0000076952 | ARTO.PA | ARTO | SBF |
| FR0000076952 | ARTO.PA | ARTO | SBF |
| FR0004045847 | ALVDM.PA | ALVDM | SBF |
| FR0004045847 | ALVDM.PA | ALVDM | SBF |
| FR0012532810 | WAGA.PA | WAGA | SBF |
| FR0012532810 | WAGA.PA | WAGA | SBF |
| FR0013240934 | ALERS.PA | ALERS | SBF |
| FR0013240934 | ALERS.PA | ALERS | SBF |
| FR0013284627 | ALARF.PA | ALARF | SBF |
| FR0013284627 | ALARF.PA | ALARF | SBF |
| FR0013447729 | VRLA.PA | VRLA | SBF |
| FR0013447729 | VRLA.PA | VRLA | SBF |
| FR0014005HJ9 | OVH.PA | OVH | SBF |
| FR0014005HJ9 | OVH.PA | OVH | SBF |
| FR001400BMH7 | TRACT.PA | TRACT | SBF |
| FR001400BMH7 | TRACT.PA | TRACT | SBF |
| FR001400BMH7 | TRACT.PA | TRACT | SBF |
