# P9.2 02d — Step 0 synthesis (Consob flag promotion)

**Goal.** Categorize the 47 Consob deals (live DB snapshot
2026-05-28) into PROMOTABLE / MIXED / OUTLIER / MANUAL_REVIEW
buckets so the 02d promotion script can route each into its
target `offer_price_quality_flag` deterministically.

**Inputs.** `data/audits/p92_02d_consob_full.csv` (47 rows, full
field set). DB at alembic HEAD `0015`. Per-deal detail in
`docs/phase-09/p92_02d_categorization.md`.

## a) Décompte par catégorie (post user-decisions 2026-05-28)

| Category | Source rule (first-match order) | Target flag | Count |
|---|---|---|---|
| **MIXED** | `deal_type = opas` (any price state) | `suspect_mixed` | 6 (4 priced + 2 NULL OPS-prefixed) |
| **MANUAL_REVIEW** | `offer_price IS NULL` OR `target_name = '[pending parse]'` | `manual_review` | 5 (3 NULL + 2 partial-ingestion) |
| **OUTLIER** | `offer_price ∉ [0.01, 10 000]` | `failed_validation` | 1 (Banco BPM 3.8B) |
| **PROMOTABLE** | else | `verified_cash` | **35** (incl. 1 with `statistical_outlier=True`) |
| **Total** | | | **47 / 47** ✓ |

Delta vs pre-decision draft (37/6/1/3):
- −2 from PROMOTABLE (the two `[pending parse]` rows: id 327 CIR
  2026, id 333 Antares).
- +2 to MANUAL_REVIEW for the same reason — if the target name
  parsing failed on the PDF, the price extraction integrity on
  the same PDF is not guaranteed; re-ingestion required before
  the deal becomes tradable.
- Health Italia (id 334) stays in PROMOTABLE but receives a
  `statistical_outlier=True` annotation in the audit CSV (price
  300 € > p95 × 3 = 107.19 €) — informational only, doesn't hold
  back the trade signal.

Net **35 deals promoted to `verified_cash`**, vs the original
pre-audit guess "~38". The audit + decision pass shaved 3 off the
estimate (1 from the OPAS-vs-cash distinction, 2 from the partial-
ingestion guard).

## b) Bounds final (validated)

**`0.01 ≤ price ≤ 10 000` EUR per share.** Justified by the
distribution of the 42 non-NULL Consob prices:

| Statistic | Value |
|---|---|
| min | 0.3375 (Beghelli small-cap) |
| p05 / p25 / median / p75 / p95 | 0.61 / 1.99 / 3.70 / 12.00 / 35.73 |
| max legitimate | 300.00 (Health Italia) |
| max with outlier | 3 828 060 000 (Banco BPM) |

- Lower 0.01 € is 34× below the observed min — safety margin
  against future parser truncation, no legitimate deal at risk.
- Upper 10 000 € catches Banco BPM (controvalore complessivo
  mis-parsed as unit price) cleanly. 7-order-of-magnitude gap
  between max legitimate (300) and the outlier means the choice
  is robust.
- Health Italia (300 €/share) flagged as edge case but kept in
  PROMOTABLE — plausible for an illiquid Italian small-cap, no
  reason to reject without visual PDF inspection.

**No adjustment to bounds proposed in the brief. Validated.**

## c) Estimation `verified_cash` — confirmed at 35 post user-decisions

The 02d promotion script will produce, deterministically:
- **35 deals** moved from `suspect_low_unverified` →
  `verified_cash` (1 with `statistical_outlier=True` trace =
  Health Italia 300 €)
- **6 deals** moved from `suspect_low_unverified` →
  `suspect_mixed` (the 7 opas-typed deals minus the Banco BPM
  outlier)
- **1 deal** (Banco BPM, id 1034) moved to `failed_validation`
- **5 deals** moved to `manual_review`:
  - 3 NULL-price (Piovan id 1039, morif id 1035, Comal id 1040)
  - 2 `[pending parse]` upstream (CIR 2026 id 327, Antares id
    333) — price was extracted but target_name parsing failed
    on the same PDF, integrity not guaranteed

Net Phase-8 trading flow impact: **+35 candidates immediately**,
+6 `suspect_mixed` candidates exposed to 02e for proper cash+share
split.

## d) Edge cases borderline (manual call needed before code)

1. **Health Italia 300 €/share** — within bounds but 8.4σ above
   the population mean. Recommend keep in PROMOTABLE per
   "bounds validated, no manual override" principle. **User to
   confirm or move to MANUAL_REVIEW.**

2. **Two `[pending parse]` target_names** (id 327 CIR 2026, id
   333 Antares 2026). Prices in bounds, deal_type cash-style →
   PROMOTABLE applies. 02d will promote the price flag; a
   separate cleanup pass should refill `target_name` from the
   PDF body. **Not a blocker for 02d.**

3. **OPS-prefixed-but-opas-typed deals** (id 342 Mediobanca /
   `ops_montepaschi`; id 344 Banca Pop Sondrio /
   `ops_Banca_Popolare_Sondrio`). DB types them `opas` but the
   `regulator_ref` prefix says `ops_` (Italian OPS = pure share
   swap, no cash leg). NULL `offer_price` is consistent with
   pure OPS. Conservative 02d treatment: `suspect_mixed`. 02e
   should resolve whether these are misclassified OPS or truly
   OPAS with a missed cash leg. **02d does not need to resolve
   this — it routes both to `suspect_mixed` either way.**

4. **Two Banca Sistema OPAS deals** (id 335 Jan 2026 at 1.80 €;
   id 326 May 2026 at 1.89 €). Likely revised/competing offers
   on the same target. Both → `suspect_mixed`. 02e to split
   cash + share legs and decide on a representative `verified_mixed`
   row.

5. **Ruby Equity / Unieuro** (id 1050). `regulator_ref` prefix
   `opsc_` (likely "OPS Condizionata"); DB `opas`. Cash leg
   9.00 € was extracted. Conservative: `suspect_mixed`; 02e to
   validate.

6. **CIR self-tender** (id 1044, 0.61 €). Issuer = Offerer.
   The price IS a real cash offer to remaining shareholders, so
   PROMOTABLE applies. No special handling.

7. **Two Eles Semiconductor deals close in time** (id 338 mare,
   id 336 eles). Likely sequential filings on the same target,
   both PROMOTABLE. Downstream Phase-8 may want to dedupe.

## e) Migration nécessaire ?

**No migration required for 02d.**

All four target flags (`verified_cash`, `suspect_mixed`,
`failed_validation`, `manual_review`) exist in:
- `src.core.enums.OFFER_PRICE_QUALITY_FLAGS` (tuple at l. 80-ish)
- The `ck_deals_offer_price_quality_flag` CHECK constraint
  (migration `0015_phase_09c_deal_consideration_pricing`)

02d's surface = a single Python script (`scripts/promote_consob_p92d.py`
or similar) issuing UPDATE statements per deal-id. No schema
change, no enum change, no new constraint.

Optional flag additions (deferred):
- `share_swap_pure` — semantic for OPS-prefixed pure share-swap
  deals. Currently routed to `suspect_mixed`; a dedicated flag
  would clarify but not change downstream filtering logic. Add
  in P10 housekeeping if needed.
- `pdf_text_extraction_failed` — semantic for the Piovan / morif /
  Comal cases. Currently routed to `manual_review`. Add in 02f
  if OCR fallback is greenlit.

## f) Decisions log (validated by user 2026-05-28)

1. **Health Italia (id 334, 300 €)** → PROMOTABLE with audit-trail
   trace `statistical_outlier=True` (gate at `price > p95 × 3 =
   107.19 €`). Promotion proceeds; downstream Phase-8 / scoring
   can surface for review without holding back the signal.
2. **`[pending parse]` rows (id 327 CIR, id 333 Antares)** →
   MANUAL_REVIEW, NOT PROMOTABLE. Rationale: if `target_name`
   parsing failed on the PDF, the price extraction integrity on
   the same PDF is suspect. Re-ingest before promotion.
3. **OPS-prefixed-but-opas-typed (id 342 Mediobanca, id 344 Banca
   Pop Sondrio)** → stay `suspect_mixed` in 02d. Reclassification
   to a dedicated `share_swap_pure` enum value = **02e scope**
   (will require an enum migration in 02e).
4. **Banca Sistema duplicate (id 335 / id 326)** → `suspect_mixed`
   in 02d. 02e decides which is the representative row /
   `verified_mixed`.
5. **No migration in 02d**. Confirmed. All 4 target flags exist
   in the current enum + CHECK constraint (migration 0015).

## Implementation gate

Step 0 closed. Proceeding to:
- 02d-B: `scripts/promote_consob_flags_02d.py` + tests
- 02d-C: dry-run → `data/audits/p92_02d_promotion_results.csv`
  for per-deal validation
- Post-validation: apply mode + score invalidation + atomic
  commits + PR.
