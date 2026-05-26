# P9.1c-bis — non-outlier BaFin re-parse (parser_version 1 → 2)

Closes the data-hygiene gap left by `p91b_decisions.md` decision (4)
("v2-on-new only"): the 25 non-outlier DE deals had survived P9.1a with the
migration default `suspect_low_unverified` flag and `parser_version = 1`,
even though the fixed parser would price them identically — confirmed by the
end-of-P9.1a sweep (40 verified_cash + 2 suspect_mixed across all 42 DE PDFs).

## Trigger
At [F] post-apply the BaFin distribution was 6 / 2 / 9 / 25 (verified_cash /
verified_mixed / manual_review / suspect_low_unverified). The 25 carried a
*default* flag, not an extraction verdict — confusing for a Phase-6 re-fit at
[G] and a latent inconsistency on the BaFin source (17 deals at v2, 25 at v1).
Re-parsing was cheap, the sweep predicted a clean promotion, and v2-on-all-of-
BaFin removes the asymmetry for the rest of Phase 9.

## Run outcome (`scripts/reparse_p91cbis.py`)
**25 / 25 promoted** to `verified_cash`. **0 / 25 price changes** above the
1% invalidation threshold — every deal's `offer_price` is identical between
the parser-v1 first-EUR-match and the parser-v2 anchored extraction (expected:
on non-outliers the first EUR in the doc *is* the Geldleistung amount because
no par-value clause precedes it). **0 scores invalidated.** No
`new_suspect_mixed` surprise: the audit's mixed-offer set (Commerzbank,
ProSieben) is complete; no hidden mixed offers in the non-outlier bucket.

CSV: `data/audits/p91cbis_reparse_results.csv` (gitignored).

## BaFin distribution after

| flag | parser_v2 count | notes |
|---|--:|---|
| `verified_cash` | **31** | 6 from [F] + 25 promoted here |
| `verified_mixed` | 2 | Commerzbank, ProSieben (P9.1c-[E]) |
| `manual_review` | 9 | P9.1c-[F] downgrades |
| **total** | **42** | all DE at `parser_version = 2` (parser_v1 = 0) |

## Effect on [G] (Phase-6 re-scoring)
**Scoring universe is unchanged at 222 labelled deals** — scoring is
flag-agnostic in V1, as established in `p91b_decisions.md`. P9.1c-bis is a
hygiene improvement, not a universe-shrinkage fix. What it *does* unlock for
[G] (optional, to discuss): a `quality_flag_encoded` feature in scoring V2,
now meaningful on BaFin (every DE deal has a parser-derived verdict) but
still default on FR/IT until P9.2 ports the same fix to AMF/Consob parsers.

## Note: FR / IT remain at default
The 148 FR + 35 IT labelled deals still carry the migration default
(`suspect_low_unverified`, `parser_version = 1`). The BaFin parser fix does
not help them — they use the AMF and Consob parsers. P9.2 (ISIN extraction
for FR/IT) is the natural place to introduce the analogous re-parse +
flag revaluation for those sources.
