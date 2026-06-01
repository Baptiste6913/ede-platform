# Phase 10 — closure summary (honest failure on V2 retrain)

**Status**: ⚠ Partial — Steps 1 + 2 delivered, Steps 3-7 aborted on empirical NO-GO
**Date**: 2026-06-01
**Branch**: `phase-10-premium-pct-wiring`
**Commits**: 3 atomic + this closure

Closes the Phase 10 sprint (P9.2 02b §9 tech-debt item: wire
`premium_pct` so future parser-quality corrections matter for the
scoring model). The fix the sprint planned to ship — V2 retrain on a
backfilled `premium_pct` feature — is **aborted** because the empirical
sample test surfaced a structural blocker the brief had not anticipated.

The two delivered steps still have independent value for a follow-up
sprint (P9.2 02c IT ISIN extraction + the future Phase 11 reliable
ticker resolver), so the branch ships the partial work + this honest
post-mortem rather than discarding it.

## 1. Executive summary

| Metric | Value |
|---|---|
| Sprint goal | Wire `premium_pct` → re-train scoring V2 (hypothesised AUC 0.611 → 0.65-0.72) |
| Delivered | ISIN extraction infrastructure + 152 `ticker_target` rows back-filled |
| Aborted | `premium_pct` compute, V2 retrain, V1 vs V2 audit |
| Hypothesis tested | "Missing tickers (FR / IT) is the bottleneck" |
| Hypothesis verdict | **Wrong** — yfinance ISIN → ticker resolution is the bottleneck |
| Sample test result | 7 / 20 raw OK (35 %), 5 / 20 real OK (25 %) after stripping 2 wrong-ticker false positives |
| Threshold required | ≥ 70 % per Option C go-criterion |

## 2. Methodology

Followed the Option C plan from `artifacts/phase-10/preflight.md`
(hybrid measure-then-decide):

| Sub-step | Commit | Outcome |
|---|---|---|
| Pre-flight | (folded into Step 1 commit) | Surfaced the blocker in advance: 183 / 222 labelled deals (FR + IT) had `ticker_target IS NULL`. Sample of 5 AMF PDFs proved ISIN extractable 5 / 5. |
| Step 1 | `0f19cc7` | ISIN regex on AMF PDFs → 148 / 148 FR labelled deals back-filled (100 %). |
| Step 2 | `c467146` | DE backfill 4 / 4 (legacy `BAFIN-<name>-<date>` refs) + `resolve_target_ticker(allow_bare_isin=True)` opt-in fallback + 9 unit tests. |
| Step 3 | `d51e76d` | Sample yfinance test on 20 deals (13 FR + 3 IT + 4 DE proportional). 35 % raw / 25 % real success rate → **NO-GO**. |
| Step 4-7 | aborted | Migration 0016 + reference_price fetcher + backfill + feature wire + V2 retrain. All skipped — see §3. |

## 3. Root cause

**The brief's diagnosis was wrong.** Reading the brief, the assumed
blocker was "FR / IT have no `ticker_target`" — fix that and we're
unblocked. The fix landed in Steps 1 + 2 (FR 148 / 148, DE 39 / 39
including the legacy 4). But the sample test in Step 3 then revealed
the actual blocker was downstream: **yfinance's ISIN → ticker
resolution is not reliable**.

Three concrete failure modes observed on the 20-deal sample (full
detail in `docs/phase-10/sample_yfinance_audit.md` §4):

1. **"Invalid ISIN number" failures on valid ISINs.** yfinance returned
   that error on ~50 % of the FR ISINs tried (GALIMMO `FR0000030611`,
   AMPLITUDE SURGICAL `FR0012789667`, COMPAGNIE DU CAMBODGE
   `FR0000079659`, …). The ISINs are valid (cross-checked against the
   PDF cover headers); yfinance's internal lookup just doesn't know
   them.

2. **Silent wrong-ticker resolution.** On 2 of the 7 "OK" rows, the
   bare-ISIN passthrough resolved to a completely different security
   without raising an error:

   | Deal | offer | ref (wrong ticker) | implied premium |
   |---|---:|---:|---:|
   | CLASQUIN 224C2186 | 142.03 € | 1.35 € | **+10405 %** |
   | COVIVIO HOTELS 224C0763 | 3.00 € | 13.14 € | **−77 %** |

   Same class of failure already documented in
   `REJECTED_TICKER_MAPPINGS` for the DE corpus (P9.1c flagged Turbon
   AG / MedNation AG as bare-ISIN false positives). The pattern is
   structural to yfinance, not a 1-off.

3. **De-listed targets returning no data.** Francotyp-Postalia,
   CompuGroup (HM listing), … Expected and acceptable, but compounds
   the success-rate hit.

The reliable 5 / 20 rows (TERACT +1 %, MEDIA 6 ×2 +3 %, ARTOIS +24 %,
H&R +1 %) all land in a plausible premium-percentage band, so the
fetcher itself is mechanically correct when yfinance does cooperate —
the failure is the resolution layer between ISIN and Yahoo ticker.

## 4. Why we aborted instead of pushing through

A V2 retrain on 5 / 20 real-success-rate input means:

- 75 % of the labelled set ships with `premium_pct = NaN`, falling back
  to the existing IterativeImputer drop behaviour → no improvement vs
  V1 on those rows.
- 10 % of the labelled set (the wrong-ticker false positives like
  CLASQUIN / COVIVIO) ships with a **+10000 % or −77 % feature value**.
  IterativeImputer + StandardScaler would propagate that as the
  dominant outlier, dragging the model into nonsense.

The dangerous case is (2): an obviously-wrong feature value lands and
the model "learns" from it. V1.1 at delta = 0 (the Phase 9.2 02b
result) is honestly worse than a V2 with silent contamination —
because V2 would look like progress without being progress.

Phase 9.2 02b's discipline ("preserve the V1 production model, ship V1.1
as audit trail") sets the bar: if we can't measure improvement we
don't promote, and if the input data isn't clean we don't train.

## 5. Lessons learned

### Methodological

- **Sample-first strategy (Option C) saved 4-6 h of waste.** Without
  the Step 3 checkpoint, the full backfill + migration + retrain would
  have shipped 148 FR rows of garbage data into the V2 training set.
- **The wrong-ticker false positives are more dangerous than missing
  values.** Empirically, 2 / 7 of the bare-ISIN "successes" were
  silently wrong. A retrain that ignores this trade-off is worse than
  a retrain that does not happen.
- **Honest "no-go" reporting > faking forward progress.** The whole
  point of the 70 % threshold was to make the no-go answer trivial to
  arrive at. The threshold did its job.

### Architectural

- **yfinance is an EOD-close fetcher, not an ISIN resolver.** It
  accepts ISINs because Yahoo's symbol-search backend sometimes maps
  them, but reliability outside US large-caps is poor. The repo's own
  `REJECTED_TICKER_MAPPINGS` already documented this for the DE
  P9.1c work — we re-discovered the same lesson at corpus scale.
- **"Looks like data" can be worse than "no data".** A returned price
  with the wrong ticker is silent contamination; an `Invalid ISIN`
  error is loud and routes to fallback.
- **Infrastructure gap before feature gap.** The premium_pct feature
  itself is trivial to compute once `reference_price` is reliable. The
  reliability gap is upstream — a dedicated ISIN→Yahoo-ticker mapping
  service (curated, validated, monitored) is the prerequisite the
  brief assumed we already had.

## 6. Deliverables retained (Phase 10 independent value)

The three commits ship work that is reusable even with the V2 retrain
aborted:

1. **`scripts/p10_isin_extraction_fr.py`** — reusable for the
   roadmapped P9.2 02c (IT ISIN extraction from Consob PDFs follows
   the same shape: header regex + first-match + DB upsert). 100 %
   success rate on the AMF corpus.
2. **`scripts/p10_isin_extraction_de_backfill.py`** — same shape for
   the 4 DE legacy `BAFIN-<name>-<date>` filings.
3. **DB enrichment** — 152 `ticker_target` rows back-filled
   (148 FR + 4 DE). These rows are now ready to consume any future
   reliable ticker resolver (Phase 11 below) without re-running the
   PDF parsing.
4. **`resolve_target_ticker(allow_bare_isin=...)`** + 9 unit tests —
   opt-in bare-ISIN fallback with the `REJECTED_TICKER_MAPPINGS` guard
   preserved. The Phase 9 strict-map behaviour is unchanged for
   existing callers.

`get_close_eur` (P9.1c) was not touched — proven reliable when the
input ticker is right, no work needed there.

## 7. Tech debt opened for Phase 11

**Phase 11 scope** — reliable ISIN → Yahoo / EOD-ticker mapping
service.

Options to evaluate, in order of effort:

1. **OpenFIGI free tier** (Bloomberg's open mapping API,
   1 000 requests / day free). Sample-test on 50 mixed-jurisdiction
   ISINs from the 222 labelled set. If ≥ 85 % success and price
   round-trip via yfinance is internally consistent → standardise as
   the resolver. ~3-4 h evaluation sprint.
2. **Manual curation** — research ~180 unique ISINs (148 FR +
   ~30 DE outside the curated map + 35 IT once 02c lands) one-by-one
   via Yahoo search + cross-check. Multi-hour but deterministic. The
   one-time cost is bounded; the result is committed into the
   existing `TARGET_TICKER_MAP` and unblocks every future sprint.
3. **EOD Historical Data** ($20 / mo subscription). Cleaner ISIN
   resolution + EOD prices in a single API. Operational cost — only
   if (1) + (2) both fall through.

**Recommended sprint**: option (1) first (free + fast to evaluate),
fall back to option (2) for the residual.

**P9.2 02c stays separately scoped** — IT ISIN extraction from Consob
PDFs is independent and lands the 35 missing IT `ticker_target` rows
regardless of which Phase 11 resolver wins.

## 8. Files

### Tracked

- `artifacts/phase-10/preflight.md` (199 lines) — infra inventory +
  sample test rationale + 3 scope options
- `scripts/p10_isin_extraction_fr.py`
- `scripts/p10_isin_extraction_de_backfill.py`
- `scripts/p10_sample_yfinance_test.py`
- `src/pricing/target_ticker_resolver.py` (modified — `allow_bare_isin`)
- `tests/pricing/test_target_ticker_resolver.py` (new — 9 tests)
- `docs/phase-10/isin_extraction_fr_audit.md`
- `docs/phase-10/sample_yfinance_audit.md`
- `docs/phase-10/closure_summary.md` (this file)

### Gitignored (audit trail, local only)

- `data/audits/p10_isin_extraction_fr.csv`
- `data/audits/p10_isin_extraction_de_backfill.csv`
- `data/audits/p10_sample_yfinance_test.csv`

### Schema state

- `alembic_version` : **0015** (unchanged — migration 0016 was planned
  but never landed because reference_price columns are not consumed
  without a reliable resolver).

## 9. Commits

| # | SHA | Subject |
|---|---|---|
| 1 | `0f19cc7` | `feat(phase-10): ISIN extraction FR from PDFs + ticker_target backfill` |
| 2 | `c467146` | `feat(phase-10): DE ticker_target backfill + bare-ISIN resolver fallback` |
| 3 | `d51e76d` | `feat(phase-10): sample yfinance test on 20 deals — NO-GO at 35% success` |
| 4 | (this) | `docs(phase-10): closure summary — honest failure on V2 retrain` |

## 10. Next sprint

- **Phase 11** (priority) : OpenFIGI evaluation → reliable ISIN →
  Yahoo / EOD ticker mapping. Unblocks Phase 10's V2 retrain ambition.
- **P9.2 02c** (parallel-runnable) : ISIN extraction IT from Consob
  PDFs, same shape as Phase 10 Step 1. Adds 35 rows to the
  `ticker_target` pool for whichever Phase 11 resolver wins.
- **V2 retrain** : deferred until Phase 11 ships a resolver that
  passes the same ≥ 70 % sample-test go-criterion.
