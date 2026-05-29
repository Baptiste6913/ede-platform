# Phase 9.2 02a — closure summary (AMF parser + pipeline wiring)

Closes the P9.2 02a sprint (AMF offer-price regex fix + end-to-end
pipeline wiring + 730-deal backfill + integration tests + closure doc).
Branch `phase-09-02a-amf-wire-parser` ready for PR.

## 1. Scope delivered

Five atomic commits on branch `phase-09-02a-amf-wire-parser`:

| # | SHA | Subject |
|---|---|---|
| 1 | `fc6278c` | `fix(amf-parser): accept integer prices + NBSP + exclude valeur nominale context` |
| 2 | `f65804c` | `feat(amf): wire extract_pdf_metadata into bdif_poller + derive quality flag` |
| 3 | `bb628b3` | `feat(scripts): backfill_p92_02a re-parse 730 FR + invalidate scores` |
| 4 | `cc2ca4c` | `test(amf): end-to-end pipeline integration tests for P9.2 02a wiring` |
| 5 | (this) | `docs(p92-02a): closure summary with measured results + false positive recalibration` |

What landed:

- **Commit #1** — three regex fixes in `src/ingestion/amf/parser.py`:
  - decimals optional (recovers bare integer prices "28 €", "82 €");
  - `[ \xa0\.]` char class → `[\s.]` (real NBSP support, the original
    matched the literal chars `\`, `x`, `a`, `0`);
  - `_NOMINAL_VALUE_RE` exclusion (80-char lookback, mirror of the
    BaFin P9.1a Grundkapital guard).
  - 14 unit tests in `tests/ingestion/amf/test_parser_p92_02a.py` incl.
    1 pinning test (`test_known_false_positives_deferred_02b`) that
    documents the surviving FPs so a future fix breaks it on purpose.

- **Commit #2** — service-layer wiring in
  `src/ingestion/amf/{bdif_poller.py, service.py}`:
  - `BdifPoller.run_once` now parses every downloaded PDF and passes the
    `ParsedMetadata` to `upsert_deal_from_bdif` (mirror of Consob
    `poller.py:165`).
  - `_derive_quality_flag` helper + AMF bounds
    `PRICE_LOWER_AMF=0.01` / `PRICE_UPPER_AMF=100_000` +
    `PARSER_VERSION_02A=2` constants in `service.py`.
  - **New-deal path** populates `offer_price`, `currency`,
    `offer_price_quality_flag`, `parser_version` on insert.
  - **Existing-deal path** is idempotent: only rows still at the
    migration-0015 default (`suspect_low_unverified`) are back-filled;
    already-promoted flags (`verified_cash`, `failed_validation`,
    `manual_review`, ...) are never overwritten by a re-poll.
  - 7 integration tests in `tests/ingestion/amf/test_service_p92_02a.py`.

- **Commit #3** — `scripts/backfill_p92_02a.py`:
  - dry-run by default, `--apply` commits per-deal + invalidates the
    `scores` cache;
  - mirror of P9.1a backfill pattern; **true idempotence** via
    `parser_version < PARSER_VERSION_02A` guard in the SELECT (a
    re-run after a successful apply matches zero rows);
  - dedicated `create_async_engine` without `pool_pre_ping` to dodge
    the sync-via-greenlet ping that misfires in this standalone script
    context.

- **Commit #4** — `tests/ingestion/amf/test_pipeline_p92_02a_e2e.py`:
  - 7 end-to-end integration tests exercising `extract_pdf_metadata`
    → `upsert_deal_from_bdif` → DB the way `BdifPoller.run_once` does;
  - 2 cases on real corpus PDFs (TIPIAK 224C0830 = 82 €,
    BALYO 226C0020 = silent miss);
  - 5 cases injecting fabricated `ParsedMetadata` to drive paths
    (outlier, pre-existing flag classes) with no naturally-occurring
    fixture in the corpus.

## 2. Résultats mesurés sur 730 deals FR

Apply (commit #3) on the live DB. Same numbers as the dry-run, zero drift.

### Distribution par new_flag

| Flag | Count | % | Notes |
|---|---|---|---|
| **`verified_cash`** | **596** | **81.6%** | well above the pre-02a 54.8% estimate (sample-extrapolated) |
| **`suspect_low_unverified`** | **133** | **18.2%** | parser silent — first-5-pages D&I without an explicit offer clause (BALYO, MEDIA 6, TERACT, POULAILLON, EEM, ...) |
| **`failed_validation`** | **1** | **0.1%** | NEOEN 225C0223, OCEANE controvalore 105 000 € > upper bound |
| **Total** | **730 / 730 ✓** | | all at `parser_version=2` |

```
 offer_price_quality_flag | parser_version | count
--------------------------+----------------+-------
 failed_validation        |              2 |     1
 suspect_low_unverified   |              2 |   133
 verified_cash            |              2 |   596
```

### Distribution des prix extraits (verified_cash + failed_validation)

| Stat | Value (EUR) |
|---|---|
| count | 597 |
| min | 0.01 |
| p05 | 0.50 |
| **median** | **17.15** |
| p95 | 315 |
| max | **105 000** (NEOEN OCEANE, sole `failed_validation`) |

### Scores invalidés : **247**

(Not every FR deal carried a prior score — Phase 6 had scored a subset.
The Phase-6 re-score is independent of this commit; per the 02d lesson
the predictions probably do not move, the invalidation is kept as
architectural discipline because `offer_price` changed under the score.)

### Cross-jurisdiction volume post-02a

| Jurisdiction | `verified_cash` |
|---|---|
| FR (post-02a) | **596** |
| IT (post-02d) | 35 |
| DE (post-02c P9.1c) | 33 |
| **Total** | **664 verified-cash candidates** |

(vs ~470 estimated in pre-02a planning; the integer-price fix
recovered far more deals than the original sample-based projection.)

## 3. Frontière bound 100 000 validée empiriquement

`PRICE_UPPER_AMF=100_000` was widened from the original 1 000 cap on
the strength of the LV GROUP verification (commit #1 SELECTIRENTE
session). The 730-deal apply confirms the calibration: **a single deal
lands `failed_validation`** (NEOEN OCEANE 105 000), and every high-price
outlier in the verified-cash distribution traces back to a documented
small-cap retrait. Frontier audit (top of the price tail):

| Ref(s) | Target | Extracted | Verdict | Context |
|---|---|---|---|---|
| 225C0223 | NEOEN | 105 000 | **`failed_validation` ✓** | OCEANE controvalore artefact (NBSP-parsed by commit #1, then rejected by the bound) |
| 221C0903, 221C1314 | FINANCIERE AGACHE | 44 000 | verified_cash legitimate | Arnault holding micro-flottant (0,07%) retrait obligatoire |
| 225C0739, 225C0117 | SIF DE L'ARTOIS | 10 627 | verified_cash legitimate | surenchère branche numéraire ("10 627 €, au lieu de 9 300 €") |
| 222C0375, 221C3476 | LV GROUP | 10 000 | verified_cash legitimate | retrait LVMH sur small-cap radiée 1992 (Finexsi-validated) |
| 224C1625 | SIF DE L'ARTOIS | 9 300 | verified_cash legitimate | offre initiale branche numéraire OPA-OPE |
| 220C5350, 221C0271 | BOUYGUES CONSTRUCTION* | 3 950 | verified_cash legitimate | retrait sur **filiale BOUYGUES CONSTRUCTION** (430 actions, 0,03% du capital), pas BOUYGUES SA |

\* The `target_name` field stores "BOUYGUES" (truncated during ingest),
not "BOUYGUES CONSTRUCTION". The PDF clearly identifies the filiale
("L'initiateur s'engage à acquérir... actions BOUYGUES CONSTRUCTION...
0,03% du capital").

**No borderline case detected between 10 000 (legitimate top) and
100 000 (bound).** Pattern in the data: every extracted price above
1 000 € on AMF FR is a small-cap holding retrait — Arnault holdings,
LVMH retraits, group filiales. None are pricing artefacts.

## 4. Bilan dry-run comparatif before/after regex (commit #1)

Measured on the 80-deal stratified audit sample, recompiled in
`scripts/p92_02a_regex_impact.py` and
`scripts/p92_02a_regex_impact_post_fix.py`:

| Category | Count | Notes |
|---|---|---|
| **Recovered** (`silent_miss` → extracted correct) | **17** | TIPIAK 82, PRODWARE 28, TARKETT 20, ALTUR 11, PCAS 8, CIFE 61, SQLI'24 54, OVH 9, GROUPE FLO 21, ESKER 262, SOMFY 143, UNIBEL 1180, TARKETT'25 17, TARKETT'25 16, POULAILLON 9, COGELEC 29, LV GROUP 10000 |
| **Corrections** of pre-existing false positives | **5** | MONCEY 5.83→133, SQLI 32.04→31, LISI 0.15→27, VERALLIA 1.70→30, SELECTIRENTE 86.80→89 |
| **Pre-existing FPs maintained** (deferred 02b) | **2** confirmed | FNAC DARTY 36 ×2 (real 81.12), TRAVEL TECHNOLOGY INTERACTIVE 2.34 ×2 (real 2.85) |
| **New FPs introduced** | **0** | the candidate SELECTIRENTE 63 nominal was excluded by the new guard; SELECTIRENTE 89 is the legitimate cum-div price |

**Ratio gain/coût net : 22:0 (17 recovered + 5 corrections / 0 new FP).**

## 5. AVERTISSEMENT FAUX POSITIFS — recalibrated on full corpus

The original pre-02a sample of 25 audited deals showed 6 mismatch-of-
anchoring cases (24%). The commit #1 regex fix corrected 5 of those
(MONCEY/SQLI/LISI/VERALLIA/SELECTIRENTE were anchoring artefacts of
the old regex, not parser intelligence gaps). One TESSI case
previously flagged as FP turned out to be the correct dividende-attaché
price (see below). The **residual FP rate on the verified sample is
1–2 cases per 25 (≤8%)**.

### Liste nominative des FPs résiduels — scope 02b

These rows are stored in DB as `verified_cash` (the bound passes them)
but the extracted value does not match the principal `s'engage à
acquérir au prix de X` clause of the PDF. Positional anchoring is
required.

| Ref | Target | DB price | Real price | Why mis-anchored |
|---|---|---|---|---|
| 226C0287 | FNAC DARTY | 36 | 81.12 | regex catches a residual `36 €` mention before the principal clause (BSA / dividende-class) |
| 226C0644 | FNAC DARTY | 36 | 81.12 | same pattern, different surenchère filing |
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | 2.85 | regex catches the *quoted previous price* ("au prix unitaire relevé de 2,85 €, contre 2,34 € initialement annoncé") — finditer picks the second match in the sentence |
| 224C1289 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | 2.85 | same surenchère pattern |
| 218C1907 / 218C2028 / 223C0160 / 222C2665 | SERMA GROUP | 229.19 / 430 | TBC | multiple SERMA filings at three distinct prices; 218C2028 (`229.19`) seems anchored on an unrelated mention; **investigation deferred to 02b** |

### Removed from the previous FP list

- **TESSI 219C0051 / 219C0215 (160 €)** — **NOT a FP**. PDF: *"au prix
  unitaire de 160 euros (le dividende exceptionnel et l'acompte sur
  dividende envisagés pour un montant total de 42,70 € par action
  étant détachés)"*. Exactly the SELECTIRENTE pattern: 160 = offer
  price (cum-div), 42.70 = the dividend being detached. The dataset
  convention (see §7 Note de définition) is to store the announced
  cum-div price, so 160 is correct.

- **BOUYGUES 220C5350 / 221C0271 (3 950 €)** — **NOT a FP**. PDF
  confirms a retrait obligatoire on the unlisted filiale BOUYGUES
  CONSTRUCTION (430 actions, 0,03% du capital). The `target_name`
  field is truncated to "BOUYGUES" but the deal is on the filiale.

### Extrapolation to the 596 verified_cash population

- 4 confirmed FPs (FNAC DARTY ×2, TRAVEL TECH ×2) = 0.67% of the 596.
- SERMA GROUP 5 filings + a long tail of un-audited rows = realistic
  upper bound **6–10%**, i.e. **~35–60 deals** with an incorrect
  anchor on the 596 verified_cash population (best-effort estimate; a
  systematic re-audit happens with 02b regression).

> **Phase-8 trading caveat.** Until 02b ships the positional anchoring
> fix, any AMF trading signal on `verified_cash` deals must either
> (i) wait for the 02b merge, or (ii) filter on a re-audited whitelist
> for the specific tickers being traded. The 4 confirmed FPs above all
> sit at prices well below their real values, so naïve trading on the
> wrong `offer_price` would systematically under-quote the spread.

### Conditions de levée du gate Phase-8 AMF

Phase-8 trading sur AMF reste gated par principe de précaution (4 FPs
confirmés + SERMA TBC + possibles cas non détectés sur la longue queue).
Deux voies de levée :

1. **Merge 02b** (verb discriminator `s'engage` vs `a acquis` +
   investigation positional anchoring sur surenchères) — voie nominale,
   corrige les FPs estimés à la racine.
2. **Vérification exhaustive des 596 `verified_cash`** — échantillonnage
   stratifié élargi (~100 deals) avec vérité terrain manuelle, validant
   que le taux FP < 1%. Voie alternative si 02b est repoussé.

État actuel (4 FPs confirmés = 0.67% sur 596) : une activation Phase-8
AMF **avec filtre nominatif** excluant les 4 FPs connus (FNAC DARTY ×2,
TRAVEL TECH ×2) + SERMA GROUP en quarantaine est *techniquement
acceptable* mais **nécessite une validation séparée (P10 architecture
review) avant production** — pas une décision à prendre en sprint.

## 6. Acquis méthodologiques

- **Dry-run comparatif before/after avant tout élargissement de
  regex critique** — `scripts/p92_02a_regex_impact*.py` measured the
  delta on the audit sample *before* the regex landed in prod, surfaced
  SELECTIRENTE as a corner case (later reclassified as a correction
  rather than a new FP), and produced the 22:0 ratio that drove the
  go decision. Pattern to apply to every future parser-regex change
  with non-trivial scope.

- **Idempotent backfill — double guard.** The initial WHERE clause of
  the backfill query only filtered on `offer_price_quality_flag = default`
  and produced "DB-coherent but pointlessly re-writing" behaviour on
  re-run. The fix added `parser_version < PARSER_VERSION_02A` — a
  *true* idempotence guard that matches zero rows on a second apply.
  Mirror of P9.1a; pattern to apply in 02e and every future backfill.

- **Bounds per-jurisdiction, empirically calibrated.** BaFin has no
  numeric bounds (semantic anchoring on cash-clause verbs);
  Consob = [0.01, 10 000] (commit P9.2 02d); AMF = [0.01, 100 000]
  (this sprint, widened for LV GROUP-class small-cap retraits). Do
  not blindly copy a bound from one jurisdiction to another — calibrate
  on the corpus.

- **Manual ground truth on stratified sample + dry-run comparator =
  primary defense against FPs introduced by regex widening.** Five
  PDFs read by hand in commit #1 (SQLI, LISI, VERALLIA, LV GROUP +
  SELECTIRENTE) caught a misdiagnosis of SELECTIRENTE that would have
  been recorded as a new FP without the read.

- **Service-layer helper for quality flag (Option A) — parser
  untouched.** Putting `_derive_quality_flag` in `service.py` rather
  than the parser keeps the parser stateless and lets the bounds /
  routing evolve with the service contract. The parser only returns
  raw extraction; the service decides what to do with it.

## 7. Dette résiduelle ouverte

| Sprint | Scope | Affects 02a how? |
|---|---|---|
| **02b** | Verb discriminator (`s'engage` vs `a acquis`) + `par action` qualifier + investigation of positional anchoring (`finditer` returns first match — wrong on surenchère filings where the previous price is quoted before the new one). | Corrects the ~35–60 estimated FPs on the 596 verified_cash population. Does NOT change the verified_cash volume — only re-points which prices are stored. |
| **02c** | Extract ISIN from the AMF page-1 header (pattern `<ref>-<ISIN>-OP*`) on the 730 deals. | Independent of 02a (no interaction with parser/offer_price). |
| **02e** | Consob OPAS structuration cash+share (already documented in P9.2 02d closure). | Independent of 02a. |
| **02f** (conditional) | OCR Tesseract fallback if `pdf_text_extraction_failed > 5%` long tail post-02a / 02b / 02d. **Current state: 133 `suspect_low_unverified` ≈ 18% — but spot-checked silent_miss rows (BALYO, MEDIA 6, TERACT, POULAILLON, EEM) are *legitimate* D&I without an offer clause in the first 5 pages, not OCR failures. 02f probably unnecessary.** |

### Note de définition

`offer_price` stores the **announced cum-dividend offer price** (the
value in the principal `s'engage à acquérir au prix de X €` clause).
The ex-dividend net effectively paid after coupon detachment is NOT
modeled separately. Two concrete cases in the corpus:

- SELECTIRENTE 218C2043 → 89 € cum-div (stored), 86.80 € ex-div (not stored)
- TESSI 219C0051 → 160 € cum-div (stored), 117.30 € ex-div (not stored)

Convention chosen for dataset consistency; revisit if net-yield analytics
become a P10 requirement.

### Architecture P10 — to document

- per-jurisdiction bounds (the `PRICE_LOWER_*` / `PRICE_UPPER_*`
  constants spread across `service.py` files);
- backfill idempotence convention (double guard: flag + parser_version);
- dry-run comparator pattern as a prerequisite for regex changes.

## 8. Liens artefacts

Audit CSVs (gitignored, regenerable from the scripts):

- `data/audits/p92_02a_sample.csv` — 80-deal stratified audit sample
- `data/audits/p92_02a_amf_dryrun_extended.csv` — pre-fix sample audit
- `data/audits/p92_02a_regex_impact_before_after.csv` — commit #1 delta
- `data/audits/p92_02a_regex_impact_post_fix.csv` — confirms 22:0
- `data/audits/p92_02a_bound_validation.csv` — bound calibration on the 80-deal sample
- `data/audits/p92_02a_backfill_results.csv` — last script run output
- `data/audits/p92_02a_high_price_verification.csv` — FINANCIERE AGACHE / ARTOIS context

Phase 9.2 02a docs (tracked):

- `docs/phase-09/p92_02a_step0_synthesis.md` — pre-sprint scoping
- `docs/phase-09/p92_02a_pipeline_audit.md` — pipeline state pre-wiring
- `docs/phase-09/p92_02a_dryrun_synthesis.md` — dry-run findings synthesis
- `docs/phase-09/p92_02a_closure_summary.md` — this file
