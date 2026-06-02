# Phase 10 Step 3 — yfinance sample test audit

Tests the full chain `resolve_target_ticker(allow_bare_isin=True) -> get_close_eur(...)` on 20 labelled deals (mix FR / IT / DE proportional). Drives the Option C go / no-go decision for the full Step 4 backfill.

## 1. Success rates

| Jurisdiction | Sample | OK | Rate |
|---|---:|---:|---:|
| FR | 13 | 6 | 46.2 % |
| IT | 3 | 0 | 0.0 % |
| DE | 4 | 1 | 25.0 % |
| **TOTAL** | **20** | **7** | **35.0 %** |

## 2. Status distribution

| Status | Count |
|---|---:|
| `no_data` | 10 |
| `no_ticker` | 3 |
| `ok` | 7 |

## 3. Implied premium_pct distribution (sanity preview)

Computed as `(offer_price - reference_price) / reference_price * 100`.

- count : 6
- min   : -77.16 %
- median: 2.12 %
- max   : 10405.18 %
- stdev : 4251.93 %
- outliers (|premium| > 100 % or < -50 %) : 2 -- investigate before Step 4.

## 4. Per-deal detail

| Jur | Ref | Target | Ticker resolved | Offer | Ref EUR | Eff date | Premium % | Status |
|---|---|---|---|---:|---:|---|---:|---|
| FR | 225C0129 | EXCLUSIVE NETWORKS | FR0014005DA7 |  |  |  |  | `no_data` |
| FR | 224C0817 | IDSUD | FR0000062184 | 1.750000 |  |  |  | `no_data` |
| FR | 225C1285 | AMPLITUDE SURGICAL | FR0012789667 | 6.250000 |  |  |  | `no_data` |
| FR | 226C0550 | TERACT | FR001400BMH7 | 3.120000 | 3.09 | 2026-04-17 | 0.97 | `ok` |
| FR | 224C0762 | MONTAGNE ET NEIGE DEVELOP | FR00140050Q2 |  |  |  |  | `no_data` |
| FR | 224C0763 | COVIVIO HOTELS | FR0000060303 | 3.000000 | 13.135802 | 2024-05-30 | -77.16 | `ok` |
| FR | 226C0531 | MEDIA 6 | FR0000064404 |  | 9.2 | 2026-04-15 |  | `ok` |
| FR | 224C1562 | GALIMMO | FR0000030611 | 14.830000 |  |  |  | `no_data` |
| FR | 225C1629 | AMPLITUDE SURGICAL | FR0012789667 | 6.250000 |  |  |  | `no_data` |
| FR | 224C2186 | CLASQUIN | FR0004152882 | 142.030000 | 1.352 | 2024-11-05 | 10405.18 | `ok` |
| FR | 225C0739 | SOCIETE INDUSTRIELLE ET F | FR0000076952 | 10627.000000 | 8550.0 | 2025-11-27 | 24.29 | `ok` |
| FR | 224C1903 | COMPAGNIE DU CAMBODGE | FR0000079659 |  |  |  |  | `no_data` |
| FR | 226C0645 | MEDIA 6 | FR0000064404 | 9.890000 | 9.6 | 2026-05-06 | 3.02 | `ok` |
| IT | CONSOB-opa_morif_20250407 | Monti Riffeser Srl |  |  |  |  |  | `no_ticker` |
| IT | CONSOB-opa_Beghelli_20250314 | Beghelli Spa |  | 0.337500 |  |  |  | `no_ticker` |
| IT | CONSOB-opa_cir_20241125 | CIR Spa |  | 0.610000 |  |  |  | `no_ticker` |
| DE | BAFIN-DE000FPH9000-20250731 | Francotyp-Postalia Holdin | DE000FPH9000 | 2.800000 |  |  |  | `no_data` |
| DE | BAFIN-DE000A2E4T77-20250630 | H&R GmbH & Co. KGaA | DE000A2E4T77 | 5.000000 | 4.94 | 2025-06-27 | 1.21 | `ok` |
| DE | BAFIN-DE000A288904-20250523 | CompuGroup Medical SE & C | DE000A288904 | 22.000000 |  |  |  | `no_data` |
| DE | BAFIN-DE000A288904-20241223 | CompuGroup Medical SE & C | DE000A288904 | 22.000000 |  |  |  | `no_data` |

## 5. Go / no-go (Option C criterion)

- Threshold: overall success rate ≥ 70 %.
- **NO-GO** (35.0 % < 70 %). Scope-back options to validate with user:
  - **A** — DE-only Phase 10 (skip FR + IT in backfill). 39 deals = 17.6 % of training set.
  - **B** — extend IT ISIN extraction (mirror Step 1 on Consob PDFs) before scope decision.
  - **C** — extend the curated TARGET_TICKER_MAP with the failing bare-ISIN cases (manual research, longer).
