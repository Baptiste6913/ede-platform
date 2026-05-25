# P9.1a — BaFin offer_price parser fix (summary)

Fixes the BaFin `offer_price` parser and backfills the misparsed deals. Diagnosis
in `p91a_cluster_1_diagnosis.md` + `p91a_pattern_mixed_diagnosis.md`. Out of
scope (→ P9.1b): structuring mixed offers into cash + share legs, external price
validation, and Phase-6 re-scoring.

## What changed

### (a) Bug 1 — anchor the cash price, not the par value
`_extract_price` returned the **first** EUR amount in the first 10 pages. For
German *Stückaktien* that is the per-share par value
("anteiliger Betrag am Grundkapital … EUR 1,00"), printed before the offer.
Replaced by `_extract_offer` / `_extract_cash_price`, anchored on a cash clause
(`Angebotspreis|Angebotsgegenleistung|Geldleistung|Geldbetrag|Barangebot … EUR X`),
handling both EUR-first/amount-first orders and BaFin's line breaks. No cash
clause ⇒ `offer_price` NULL with flag `suspect_low_unverified` (never the par
value).

### (b) Bug 2 — flag mixed / share-exchange offers
Consideration was modelled as a single EUR scalar; share legs were lost.
`_OFFER_MIXED_RE` detects `Gewährung/Gegenleistung … von <ratio> (Stück)aktien
der <Erwerber>` and is checked **first** (a cash+share offer also has a cash leg
that must not be stored alone). Such offers get `offer_price` NULL +
`suspect_mixed`. Connector covers phrasing variants ("Gewährung einer
Gegenleistung von …", "in Form von …"); the `von <digit>` guard keeps cash
clauses ("von EUR x,xx") out of this path.

### (c) Gegenleistung in the cash set
Some offers phrase the cash price as "Gegenleistung in Höhe von EUR X je Aktie"
(Klassik Radio). `Gegenleistung` was missing from the cash anchor, so the
backfill first nulled Klassik. Added it; no clash with the share-exchange use
because the mixed check runs first and keys on plural "Aktien der", whereas a
cash clause ends in singular "je Aktie".

### (d) Infrastructure
- Migration **0014** — `deals.offer_price_quality_flag` ENUM
  (verified_cash, suspect_mixed, suspect_low_unverified, failed_validation,
  manual_review) + `deals.parser_version` SMALLINT.
- `PARSER_VERSION = 2`; the re-parse bumps it so backfills can target stale rows.
- `scripts/audit_offer_price.py` (Step-0 audit) + `scripts/backfill_p91a.py`
  (re-parse + update + score invalidation), both idempotent.

## Backfill results (17 audit outliers, against `ede`)

3 corrected · 2 nulled (suspect_mixed) · 12 unchanged (verified_cash). Full CSV:
`data/audits/p91a_backfill_results.csv` (gitignored).

| deal | target | old → new | flag | action |
|---|---|---|---|---|
| 1070 | Linus | 1.00 → 1.76 | verified_cash | corrected |
| 1078 | DFV | 2.00 → 6.60 | verified_cash | corrected |
| 1079 | infas | 1.00 → 6.80 | verified_cash | corrected |
| 348 | Commerzbank | 1.00 → ∅ | suspect_mixed | nulled |
| 1059 | ProSieben | 4.48 → ∅ | suspect_mixed | nulled |
| 1071 | Klassik Radio | 3.70 → 3.70 | verified_cash | unchanged |
| +11 | small-caps | unchanged | verified_cash | unchanged |

Linus/infas/DFV were all par-value captures (1,00 / 1,00 / **2,00**). The 12
unchanged confirm genuine sub-€5 small-caps — false positives of the Step-0
magnitude threshold, not misparses.

**Scores**: 5 invalidated (the 3 corrected + 2 mixed). Klassik's score was also
cleared by the first (buggy) backfill run; harmless — all re-scored in P9.1b.

`SELECT count(*) FROM deals WHERE parser_version = 2` ⇒ **17** (exactly the
backfilled set; no stray re-parses).

## Synonym sweep (false-null class closed)

The fixed parser was run over **all 42 DE PDFs**: 40 `verified_cash` +
2 `suspect_mixed` + **0 `suspect_low_unverified`**. No deal falls through, so no
further cash synonyms (Abfindung, Kaufpreis, Erwerbspreis, …) are needed for the
current DE population. (Note: there is no `prospectus_text` column — text is read
from the PDF at parse time, so the sweep runs the parser, not SQL.)

## Gotcha — alembic revision-ID reuse (`0014`)

Phase 8 had a different migration `0014` (`deals_is_test_deal`) that was reverted
before merge (`git reset` in the Phase-8 cleanup). The integration test DB
`ede_test` had been stamped `alembic_version = '0014'` by that abandoned
migration. This new `0014` reuses the same revision ID, so alembic believed
`ede_test` was already at head → `upgrade head` was a no-op and the new columns
were never created (and `downgrade` failed on a non-existent column).

Fix: rebuild the test DB (`DROP SCHEMA public CASCADE` + `alembic upgrade head`).
`ede` (live) was unaffected (it had been downgraded to `0013` during the Phase-8
cleanup before this branch). CI is unaffected (fresh DB each run). If you re-use
a sequential revision ID across an abandoned branch, expect this — re-stamp or
rebuild any local DB stamped by the old migration.
