# P9.2 02d — Consob 47-deal categorization

Source: `data/audits/p92_02d_consob_full.csv` (snapshot 2026-05-28),
HEAD migration `0015`.

Categorization rules (per 02d Step 0 brief):

| Category | Source criterion | Target flag |
|---|---|---|
| PROMOTABLE | `offer_price` in bounds `[0.01, 10 000]` AND `deal_type ∈ {opa_*}` (cash-type) | `verified_cash` |
| MIXED | `deal_type = opas` (mixed cash + share leg) — regardless of NULL/non-NULL price | `suspect_mixed` (final treatment in 02e) |
| OUTLIER | `offer_price` outside bounds | `failed_validation` |
| MANUAL_REVIEW | `offer_price IS NULL` AND `deal_type ∈ {opa_*}` (extraction failed) | `manual_review` |

All four target flags already exist in
`src.core.enums.OFFER_PRICE_QUALITY_FLAGS`. **No migration required for
02d.**

## 47-deal table (sorted by offer_price NULLS LAST)

| id | target | regulator_ref | offer_price | deal_type | category | target_flag |
|---|---|---|---|---|---|---|
| 1037 | Beghelli Spa | opa_Beghelli_20250314 | 0.3375 | opa_obligatoire | PROMOTABLE | verified_cash |
| 343 | Bialetti Spa | opa_bialetti_20250707 | 0.467 | opa_obligatoire | PROMOTABLE | verified_cash |
| 1044 | CIR Spa | opa_cir_20241125 | 0.61 | opa_volontaire_parziale | PROMOTABLE | verified_cash |
| 327 | [pending parse] | opa_cir_20260427 | 0.68 | opa_volontaire_parziale | PROMOTABLE | verified_cash ⚠ tgt_name |
| 1054 | Capitolium Srl | opa_vianini_20240708 | 0.86 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 346 | Il Sole 24 Ore Spa | Opa_IlSole24Ore_20250603 | 1.10 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 347 | Illimity Bank Spa | opa_illimity_20250519 | 1.414 | **opas** | MIXED | suspect_mixed |
| 1053 | Saras spa | opa_saras_20240712 | 1.60 | opa_obligatoire | PROMOTABLE | verified_cash |
| 1042 | Mittel Spa | Opa_Mittel_20250130 | 1.75 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 335 | Banca Sistema Spa | opas_Banca_Sistema_20260116 | 1.80 | **opas** | MIXED | suspect_mixed |
| 326 | Banca Sistema Spa | opa_bancasistema_20260511 | 1.89 | **opas** | MIXED | suspect_mixed |
| 1052 | Eagle Spa | opa_greenthesis_20240819 | 2.293 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1045 | Servizi Italia Spa | opa_serviziitalia_20241028 | 2.37 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1047 | Relatech Spa | opa_gemini_20241007 | 2.53 | opa_obligatoire | PROMOTABLE | verified_cash |
| 338 | Eles Semiconductor Equipment Spa | opa_mare_20251205 | 2.61 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 336 | Eles Semiconductor Equipment Spa | opa_eles_20260105 | 2.65 | opa_obligatoire | PROMOTABLE | verified_cash |
| 1036 | Cairo Communication Spa | opa_cairo_20250407 | 2.90 | opa_volontaire_parziale | PROMOTABLE | verified_cash |
| 329 | Next Re SIIQ Spa | opa_nextre_20260420 | 3.00 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1043 | Intermonte Partners Sim Spa | opa_Intermonte_Partners_SIM_20241223 | 3.04 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1046 | Defence Tech Holding S | opa_defence_20241014 | 3.15 | opa_obligatoire | PROMOTABLE | verified_cash |
| 331 | Ferretti Spa | opa_ferretti_20260316 | 3.50 | opa_volontaire_parziale | PROMOTABLE | verified_cash |
| 1041 | NVP Spa | Opa_NPV_20250210 | 3.90 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 340 | Almawave Spa | opa_almawave_20251117 | 4.30 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 330 | Solutions Capital Management Sim Spa | opa_banco_desio_20260330 | 4.61 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 333 | [pending parse] | opa_antares_20260216 | 5.00 | opa_obligatoire | PROMOTABLE | verified_cash ⚠ tgt_name |
| 341 | Palingeo | opa_palingeo_20251027 | 6.00 | opa_obligatoire | PROMOTABLE | verified_cash |
| 1057 | Civitanavi Systems Spa | opa_Civitanavi_Systems_20240527 | 6.17 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1038 | Anima Holding Spa | opa_anima_20250317 | 7.00 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1049 | IVS Group Sa | opa_grey_20240909 | 7.15 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1050 | Ruby Equity Investment Sàrl | opsc_unieuro_20240902 | 9.00 | **opas** | MIXED | suspect_mixed |
| 1051 | Alkemy Spa | opa_retex_20240819 | 12.00 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 345 | Alkemy S | opa_Alkemy_20250609 | 12.00 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 337 | Spindox Spa | opa_spindox_20251215 | 13.00 | opa_obligatoire | PROMOTABLE | verified_cash |
| 332 | Tinexta Spa | opa_Tinexta_20260223 | 15.00 | opa_obligatoire | PROMOTABLE | verified_cash |
| 1056 | Plavisgas Srl | opa_openjobmetis_20240610 | 16.50 | opa_obligatoire | PROMOTABLE | verified_cash |
| 1048 | Salcef Group Spa | opa_salcef_20241007 | 26.00 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1058 | SAES Getters Spa | opa_saes_20240527 | 26.30 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 1055 | Medica Spa | opa_medica_20240701 | 27.00 | opa_volontaire_totalitaria | PROMOTABLE | verified_cash |
| 328 | Digital Value Spa | opa_danzic_20260424 | 29.00 | opa_obligatoire | PROMOTABLE | verified_cash |
| 339 | Ala Spa | opa_ala_20251201 | 36.08 | opa_obligatoire | PROMOTABLE | verified_cash |
| 334 | Health Italia Spa | opa_health_italia_20260409 | 300.00 | opa_obligatoire | PROMOTABLE | verified_cash ⚠ edge |
| 1034 | Banco BPM Spa | ops_Banco_BPM_20250428 | **3 828 060 000** | **opas** | OUTLIER | failed_validation |
| 342 | Mediobanca-Banca di Credito Finanziario Spa | ops_montepaschi_20250714 | NULL | **opas** | MIXED | suspect_mixed ⚠ ops |
| 344 | Banca Popolare di Sondrio S | ops_Banca_Popolare_Sondrio_20250616 | NULL | **opas** | MIXED | suspect_mixed ⚠ ops |
| 1039 | Piovan Spa | opa_Piovan_20250303 | NULL | opa_obligatoire | MANUAL_REVIEW | manual_review (font cassé) |
| 1035 | Monti Riffeser Srl | opa_morif_20250407 | NULL | opa_volontaire_totalitaria | MANUAL_REVIEW | manual_review |
| 1040 | Comal Spa | opa_comal_20250217 | NULL | opa_volontaire_totalitaria | MANUAL_REVIEW | manual_review |

Total: 47 / 47 categorized.

## Category counts

| Category | Target flag | Count |
|---|---|---|
| PROMOTABLE | `verified_cash` | **37** |
| MIXED | `suspect_mixed` | 6 (4 with price in bounds + 2 NULL OPAS/OPS) |
| OUTLIER | `failed_validation` | 1 (Banco BPM 3.8B €/share) |
| MANUAL_REVIEW | `manual_review` | 3 (Piovan + morif + Comal) |
| **Total** | | **47** ✓ |

## Edge cases identified

1. **Two deals with `target_name = "[pending parse]"`** (id 327 CIR
   2026, id 333 Antares). The price is extracted and in bounds, so
   they belong in PROMOTABLE → `verified_cash`. Marked with `⚠
   tgt_name`; a separate cleanup pass should resolve the target
   name from the PDF body. Not blocking for 02d.

2. **Health Italia at 300 €/share** (id 334). Within the proposed
   `[0.01, 10 000]` envelope, p95 of the population is 35.73 € so
   this is well above. Plausible for an illiquid Italian small-cap
   (Health Italia is a low-float listed); no obvious reason to
   reject. Marked with `⚠ edge`. Recommend keep in PROMOTABLE
   unless visual PDF inspection invalidates.

3. **Two Eles Semiconductor deals close in time** (id 338
   `opa_mare` 2025-12-05 at 2.61 €; id 336 `opa_eles` 2026-01-05 at
   2.65 €). Likely a raised offer / sequential filings on the same
   target. Both PROMOTABLE; downstream may want to dedupe.

4. **Two Banca Sistema OPAS deals** (id 335 2026-01-16 at 1.80 €;
   id 326 2026-05-11 at 1.89 €). Likely revised/competing offers.
   Both MIXED → `suspect_mixed`; 02e will split cash + share legs.

5. **OPS-looking `regulator_ref` typed `opas` in DB** (id 342
   Mediobanca / `ops_montepaschi`; id 344 Banca Pop Sondrio /
   `ops_Banca_Popolare_Sondrio`). Both have NULL `offer_price`.
   The `ops_` prefix in the filename suggests CONSOB classified
   these as **OPS** (Offerta Pubblica di Scambio — pure share
   swap, no cash leg), but the DB `deal_type` is `opas` (mixed
   cash + share). Possible classification error during ingestion.
   Conservative treatment for 02d: `suspect_mixed`, flagged ⚠ ops.
   02e should:
   (a) verify whether the cash leg exists (and was missed) or these
   are truly OPS,
   (b) consider re-typing to a more precise enum value (`ope` /
   `opse` already in the deal_type enum for FR/IT share-swap
   variants — verify Italian usage).

6. **CIR self-tender** (id 1044). `OFFERENTE ED EMITTENTE: CIR
   S.p.A.` — same entity on both sides (issuer buyback). The
   `offer_price` 0.61 € is the real cash offered to other
   shareholders, so PROMOTABLE applies. No special handling
   needed.

7. **Ruby Equity / Unieuro** (id 1050). `regulator_ref` has the
   `opsc_` prefix (likely "OPS condizionata" or
   "OPA-Scambio-Condizionata"); DB types it as `opas`. Cash leg
   of 9.00 € was extracted. Conservative: MIXED → `suspect_mixed`,
   02e to validate against the PDF.

## Bounds final validation

Distribution of the 42 non-NULL Consob `offer_price` values:

| Statistic | Value |
|---|---|
| min | 0.3375 (Beghelli) |
| p05 | 0.6135 |
| p25 | 1.99075 |
| median | 3.70 |
| p75 | 12.00 |
| p95 | 35.73 |
| max (excluding outlier) | 300.00 (Health Italia) |
| max (with outlier) | 3 828 060 000 (Banco BPM) |

Proposed bounds **`0.01 ≤ price ≤ 10 000`** in EUR per share:

- **Lower bound 0.01 €**: 34× smaller than the observed min
  (0.3375). No legitimate small-cap pricing observed at this level.
  Provides safety margin against future parser bugs that might
  truncate to `0.00X`.
- **Upper bound 10 000 €**: 33× larger than max legitimate (300 €).
  Catches Banco BPM (3.8B) without rejecting any current
  legitimate price. The gap between max legitimate (300) and the
  outlier (3.8B) spans 7 orders of magnitude, so any cutoff in
  `[1 000, 1 000 000]` would work; **10 000 €** is conservative.
- Banco BPM `3 828 060 000` is parsing the **controvalore
  complessivo** (total deal size in EUR, ~€3.8B) instead of the
  per-share price. The bounds correctly catch this; the
  controvalore-vs-unit-price parser bug stays as deferred P10 debt
  unless it recurs.

**Bounds validated. No adjustment needed.**

## Migration needed?

**No.** The 4 target flags (`verified_cash`, `suspect_mixed`,
`failed_validation`, `manual_review`) all already exist in
`src.core.enums.OFFER_PRICE_QUALITY_FLAGS` and the
`ck_deals_offer_price_quality_flag` CHECK constraint (migration
0015). 02d only writes UPDATE statements on existing rows; no
schema change.

The user-suggested optional `share_swap_pure` and
`pdf_text_extraction_failed` flags would add semantic clarity:

- `share_swap_pure`: would replace `suspect_mixed` for the 2
  OPS-prefixed deals (Mediobanca, Banca Pop Sondrio) and any
  future OPS deals.
- `pdf_text_extraction_failed`: would replace `manual_review` for
  the 3 Piovan-class deals (with a more semantic name).

Both are valuable but **not required for 02d**. Recommend
deferring to a P10 housekeeping PR or to a 02f branch only if 02f
ends up needed (OCR fallback).
