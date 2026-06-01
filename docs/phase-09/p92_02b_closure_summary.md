# Phase 9.2 02b — closure summary (AMF parser positional anchoring)

Closes the P9.2 02b sprint (AMF parser FP audit + engagement-clause &
surenchère anchors + 596-deal re-parse + 64-row DB update + scoring
V1.1 zero-delta proof + closure doc). Branch
`phase-09-02b-amf-positional-anchoring` ready for PR.

## 1. Scope delivered

Nine atomic commits on branch `phase-09-02b-amf-positional-anchoring`:

| # | SHA | Subject |
|---|---|---|
| 1 | `902a246` | `docs(p92-02b): Step 0 AMF parser FP audit — 15% rate confirmed, 4 patterns cataloged` |
| 2 | `8ddf081` | `test(p92-02b): regression fixtures for 14 FP + 3 false alarm cases (failing red)` |
| 3 | `e2e66a2` | `feat(p92-02b): fix BLOCK_PURCHASE via engagement clause anchoring + OfferPriceSource enum` |
| 4 | `a9240cb` | `feat(p92-02b): fix SURENCHERE pattern for amended prices (rehaussé/relevé/modifié)` |
| 5 | `675bd9b` | `docs(p92-02b): document AMF parser conventions and extraction priority` |
| 6 | `5e9e2d2` | `feat(p92-02b): re-run parser on 596 verified_cash + comparison report` |
| 7 | `323b9a2` | `feat(p92-02b): apply parser corrections to DB (64 deals updated)` |
| 8 | `f30fb69` | `feat(p92-02b): re-train scoring V1.1 — zero delta confirmed, P10 tech debt logged` |
| 9 | (this) | `docs(p92-02b): closure summary Phase 9.2 02b` |

## 2. Executive summary

Phase 9.2 02b audited the post-02a AMF parser for positional-anchoring
false positives, fixed the root cause with two regex anchors, applied
the resulting corrections to the production DB transactionally, and
verified the side-effect on the scoring model is exactly zero (gated
by P10 feature wiring work).

| Metric | Value |
|---|---|
| Step 0 audit sample | 68 deals (60 random + 8 obligatoires) |
| Refined FP rate (random subset) | **15.0 %** (9/60) |
| Patterns identified | 4 — BLOCK_PURCHASE 43 %, SURENCHERE 29 %, DIVIDEND_TRAP 21 %, OCEANE/BSA 7 % |
| Regression fixtures | **17** (14 FP + 3 false alarms), all green post-fix |
| Anchors implemented | 2 — `engagement_clause`, `surenchere_raised` (steps 1d/1e/1f skipped as redundant) |
| Production DB corrections | **64** out of 596 verified_cash FR rows (10.7 %) |
| New parser regressions | 0 (zero `NEW_DIFFERENT`, zero `PARSER_FAIL`, zero `NEW_EXTRACT`) |
| Scoring V1.1 delta vs V1 | **0** (bit-for-bit identical — by design, see §6) |
| Tests passing (full repo) | **522** |

## 3. Methodology

### Step 0 — audit (commit `902a246`)

Stratified random sample of 68 FR `verified_cash` deals, scored
through an auto-classification heuristic, with the 19 borderline cases
pre-reviewed by Claude Code and the 7 ambiguous ones manually checked
by Baptiste (spot-checks SERMA + GALIMMO + CFI on the HIGH bucket,
full read of the 7 LOW). Refined the brut auto-classification rate
(20 %) down to the calibrated 15 % after removing 3 false alarms
(parser was right; the pre-review heuristic missed multi-bullet +
`dorénavant` formulations).

Full audit details: `docs/phase-09/p92_02b_step0_audit.md`,
`docs/phase-09/p92_02b_step0_manual_review.md`.

### Step 1 — fix + apply (commits `8ddf081`..`f30fb69`)

TDD-style sub-sprint, one anchor per commit, validated in cascade:

| Sub-step | Commit | Outcome |
|---|---|---|
| 1a | `8ddf081` | 17 fixtures pinned — 14 FP failing red, 3 false alarms passing green. Contract for the fix. |
| 1b | `e2e66a2` | `_ENGAGEMENT_CLAUSE` anchor (`s'engage à acquérir … au prix de X €`) + `OfferPriceSource` enum. Flips 12 of 14 reds to green. Subsumes BLOCK_PURCHASE / DIVIDEND_TRAP / OCEANE/BSA on the corpus. |
| 1c | `a9240cb` | `_SURENCHERE_RAISED` anchor (`rehaussé / relevé / modifié / "visées dorénavant"` + `au prix de X €`). Flips the remaining 2 MEDIA 6 reds to green. **17/17 green.** |
| 1d/1e/1f | — | **Skipped as redundant.** Every DIVIDEND_TRAP / OCEANE_BSA / multi-bullet case in the corpus carried a clean engagement clause that 1b already picked up correctly; adding separate anchors would have added attack surface for new FPs without changing the outcome. |
| 1g | `675bd9b` | `docs/PARSER_AMF.md` (275 lines): cum-dividende convention, priority order, patterns avoided, Phase 9.2 history, touching-this-parser checklist. |
| 1h | `5e9e2d2` | Re-ran the post-fix parser on every FR `verified_cash` row (596). **64 CORRECTED, 532 UNCHANGED, 0 NEW_DIFFERENT, 0 PARSER_FAIL, 0 NEW_EXTRACT.** Stop-checkpoint before the DB write. |
| 1i | `323b9a2` | Transactional DB update on the 64 CORRECTED rows. `pg_dump` taken first (`artifacts/phase-09-02b/backup-pre-parser-fix-20260601T115012Z.sql`, 1.4 MB). Dry-run + apply, both reporting 64 applied / 0 skipped / 0 failed. Post-update spot-check on 5 deals confirms. |
| 1j | `f30fb69` | Re-trained scoring V1.1 on the cleaned dataset. **Bit-for-bit identical to V1** (random_state fixed + `offer_price` not wired to features). P10 tech debt list opened. |

## 4. Parser changes

File touched: `src/ingestion/amf/parser.py`.

### `OfferPriceSource(str, Enum)` (new)

7 labels stamped on `ParsedMetadata.extraction_source` per extraction.
3 reserved (`engagement_clause_multi_bullet`, `dividend_cum_anchored`,
`fallback_last_match`) for future anchors; 4 active
(`engagement_clause`, `surenchere_raised`, `fallback_first_match`,
`no_match`). Documented in `docs/PARSER_AMF.md` §1.3.

### `_ENGAGEMENT_CLAUSE` regex (new)

```
s['’]\s*engage\w{0,6} \s+ (?:irr[ée]vocablement\s+)?
  (?:\w+\s+){0,4} [àa]\s+acqu[ée]rir
  [\s\S]{0,400}?
  <amount> \s*(?:€|euros?)
```

- Verb match `engage\w{0,6}` covers présent / imparfait (`engageait`)
  / futur / conditionnel / pluriel. Earlier `(?:e|ait|ent|...)?`
  alternation failed on `engageait` because the `e` alt consumed
  before `ait` could fire (GROUPE ETPO 225C1227).
- Lazy span `[\s\S]{0,400}?` — earlier draft with explicit optional
  `(?:au\s+prix)?(?:unitaire)?(?:de)?` groups produced pathological
  backtracking on the same GROUPE ETPO case (newline between
  `unitaire` and `de`). Simplified to lazy span + amount + € consumer
  downstream; 400-char hard cap blocks runaway match.

### `_SURENCHERE_RAISED` regex (new)

```
(?:rehauss[ée]|relev[ée]|modifi[ée]|vis[ée]es?\s+dor[ée]navant)
[\s\S]{0,100}? au\s+prix\s+(?:unitaire\s+)?(?:de\s+)? <amount> \s*(?:€|euros?)
```

The `au\s+prix` consumer after the keyword is mandatory — prevents
matches on unrelated keyword occurrences ("seuil relevé est de 30 %")
and lets the new price win even when the old price (introduced by `au
lieu de` / `initialement`) appears earlier in the same sentence.

### `_extract_offer_price` priority order

```
1. ENGAGEMENT_CLAUSE       (1b)  — s'engage à acquérir … au prix de X €
2. SURENCHERE_RAISED       (1c)  — rehaussé/dorénavant + au prix de X €
3. FALLBACK_FIRST_MATCH    (02a) — first € match w/ nominal-value 80-char guard
4. NO_MATCH                       — no euro amount in text
```

Order matters: CFI / TRAVEL TECH / NHOA 224C2193 carry both an
engagement verb AND a `prix modifié/relevé` qualifier — step 1 wins
and step 2 never overrides a valid engagement-clause hit.

## 5. Production DB impact (Step 1i)

Pre/post snapshot via direct SQL:

| Ref | Target | pre | post | Δ |
|---|---|---:|---:|---:|
| 218C1907 | SERMA GROUP | 229.19 | **235.00** | +2.5 % |
| 219C2667 | OENEO | 2.72 | **13.50** | +396 % (VNC trap → OPR price) |
| 223C2035 | TECHNICOLOR CREATIVE STUDIOS | 0.01 | **1.63** | +16200 % (BSA strike → share offer) |
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | **2.85** | +22 % (surenchère) |
| 224C1143 | ADEUNIS | 0.175 | **0.45** | +157 % (block-cession → OPAS) |

Distribution by source on the 64 corrections:

| Source | Count |
|---|---:|
| `engagement_clause` | 62 |
| `surenchere_raised` | 2 |

Row count unchanged (596 verified_cash → 596 verified_cash, all with
`offer_price IS NOT NULL`). Per-row audit log:
`data/audits/p92_02b_db_update_log.csv` (gitignored). Full counts +
rollback procedure: `docs/phase-09/p92_02b_db_update_audit.md`.

## 6. Scoring impact — zero, by design

Step 1j re-trained V1.1 on the cleaned DB. The two reasons it had to
be zero are documented in
`docs/phase-09/p92_02b_scoring_comparison.md`:

1. **Reproducibility** — every model component is seeded
   (`LogisticRegression(random_state=42)`,
   `IterativeImputer(random_state=42)`,
   `CalibratedClassifierCV(cv=3)` uses `StratifiedKFold(shuffle=False)`
   = deterministic by ordering). At fixed input the retrain is
   bit-for-bit identical to V1.
2. **Feature wiring** — none of the 14 scoring features reads
   `Deal.offer_price` directly. The closest relation is
   `bid_premium_pct = Deal.premium_pct × 100`, and `premium_pct` is
   `NULL` on every labelled deal. The 11 of 40 corrected target_names
   that are in the labelled training set (ADEUNIS, GALIMMO, GROUPE
   ETPO SA, LE BELIER, OENEO, …) carry the same NaN feature value
   pre- and post-fix.

Measured V1.1: **CV AUC = 0.6105, Brier = 0.1731**, n=128, balance
7/121 — same as V1 baseline (Phase 6 reference 0.611 / 0.173) to the
fourth decimal.

Sklearn warning surfaced during the retrain:

```
UserWarning: Skipping features without any observed values: [0 1 2]
```

→ confirms empirically that 3 of the 5 numeric features
(`bid_premium_pct`, `relative_size`, `min_acceptance_threshold`) are
100 % NaN in the training set; IterativeImputer drops them. The model
effectively trains on `events_count + days_to_expected_close + 5
categoricals + 3 booleans = 10 features`, not the 14 declared.

V1.1 artefact saved (`models/scoring_v1_1_clean_20260601T122045Z.pkl`,
55 KB) as Phase 9.2 02b audit trail. **Production stays on
`scoring_v1_20260526_p91c.pkl`**.

## 7. False alarms — pre-review heuristic limits (informational)

Three rows the Step 0 auto-classifier flagged as suspect turned out
to be **parser-correct** in 02a — kept as false-alarm fixtures so the
Step 1 fix is required to preserve them:

| Ref | Target | Pre-review missed because… |
|---|---|---|
| 226C0550 | TERACT | multi-bullet `au prix de :\n- 3,12 € par action` not matched by the pre-review regex |
| 226C0157 | TERACT | same multi-bullet shape |
| 224C1861 | NHOA | `visées dorénavant au prix unitaire de 1,25 €` formulation not matched |

All three stayed green throughout Steps 1b-1c (engagement-clause
anchor handles the bullets via the lazy span; NHOA went from
`fallback_first_match` to `surenchere_raised` — more honest provenance
on the same correct value).

## 8. Acquis méthodologiques

- **TDD with failing-red fixtures pinned before any code change**
  (Step 1a). Each subsequent commit can be summarised as "flipped X of
  Y reds to green", which made the priority/order of anchors trivial
  to debate.
- **Spot-check on non-fixture cases** (OENEO + ADEUNIS) BEFORE the DB
  update. Both confirmed the same BLOCK_PURCHASE pattern as SERMA/GALIMMO/TIPIAK
  — proved the anchor generalises beyond the fixtures.
- **Transactional DB update with explicit dry-run + apply + per-row
  defensive guard** (script bails if the row drifted off `verified_cash`
  or the current price no longer matches the CSV snapshot). Mirror of
  the P9.1a backfill pattern; raises the bar on the rollback story.
- **Empirical verification that the model side-effect is zero**, rather
  than assuming it from the closure-doc-level argument. Surfaced the
  P10 tech debt cleanly (V1 effectively uses 10 features, not 14).
- **One pattern fix subsumed three planned ones.** Steps 1d/1e/1f
  ended up redundant once 1b shipped. Acted in commit message + parser
  docstring; saves future maintenance effort + audit surface.

## 9. Dette résiduelle ouverte (P10)

To make the next batch of `offer_price` corrections matter for the
scoring model:

1. **Compute `premium_pct`** per deal at ingest. Definition:
   `(offer_price - reference_price_at_announcement) / reference_price`.
   Currently every row carries `premium_pct = NULL`.
2. **Source `reference_price_at_announcement`** — 5-day VWAP
   pre-announcement via yfinance / stooq. The fetcher infra is already
   scoped at `src/pricing/yfinance_fetcher.py`.
3. **Backfill `premium_pct`** on the 596 FR + 35 IT + 33 DE
   `verified_cash` deals so `bid_premium_pct` stops being NaN for
   every labelled row.
4. **Wire the missing price-derived features** documented but not yet
   implemented (`relative_size` needs market_cap;
   `has_irrevocable_undertaking` needs PDF section parsing).
5. **Re-train V2** with the populated feature set. Hypothesis: AUC
   moves from the 0.611 baseline into the 0.65-0.72 band.

Adjacent P10 tech debt logged during this sprint:

- Migrate `tests/parsers/test_bafin_p91a.py` to `tests/ingestion/bafin/`
  for consistency with the post-P9.1 layout (BaFin parser tests are
  the only ones left under the legacy `tests/parsers/` path).
- Remove `_extract_first_price` backward-compat shim once 02a tests +
  audit scripts have been ported to `_extract_offer_price` (the new
  triple-return signature).

## 10. Liens artefacts

### Tracked

- `src/ingestion/amf/parser.py` — `OfferPriceSource` enum + two new
  regexes + helper.
- `scripts/p92_02b_sample.py` — stratified sampling
- `scripts/p92_02b_ground_truth.py` — auto-classification on 68 deals
- `scripts/p92_02b_pre_review.py` — per-suspect pattern detection
- `scripts/p92_02b_extract_fixtures.py` — 17 fixture excerpts builder
- `scripts/p92_02b_re_run_parser.py` — 596-deal comparison driver
- `scripts/p92_02b_apply_corrections.py` — DB write (transactional)
- `scripts/p92_02b_retrain_scoring.py` — V1.1 retrain + report
- `tests/ingestion/amf/test_anchoring_fixtures_p92_02b.py` — 17 fixtures
- `tests/fixtures/p92_02b/` — 17 `*_excerpt.txt` + `README.md`
- `docs/PARSER_AMF.md`
- `docs/phase-09/p92_02b_step0_audit.md`
- `docs/phase-09/p92_02b_step0_manual_review.md`
- `docs/phase-09/p92_02b_re_run_audit.md`
- `docs/phase-09/p92_02b_db_update_audit.md`
- `docs/phase-09/p92_02b_scoring_comparison.md`
- `docs/phase-09/p92_02b_closure_summary.md` (this file)
- `models/scoring_v1_1_clean_20260601T122045Z.pkl`

### Gitignored (audit trail, local only)

- `data/audits/p92_02b_*.csv` (sample, ground_truth, comparison, log)
- `data/audits/p92_02b_*.md` (raw pre_review, manual_review,
  final_review)
- `artifacts/phase-09-02b/backup-pre-parser-fix-20260601T115012Z.sql`
  (1.4 MB, full `pg_dump` for the Step 1i rollback procedure
  documented at `docs/phase-09/p92_02b_db_update_audit.md` §6)

## 11. Next steps

- **Push + PR** : the 9 commits are local-only; push the branch and
  open the PR with the body auto-derived from this closure.
- **P10 sprint** : the tech debt list above is what unlocks the
  scoring V2 jump. Independent of further 02-series work.
- **Phase 9.2 02c (if applicable)** : per the project roadmap.
