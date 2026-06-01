# AMF Parser — Offer Price Extraction

This document describes the conventions and extraction strategy of the AMF
parser at `src/ingestion/amf/parser.py`. Scope: how `offer_price` is
extracted from AMF BDIF *notes d'information* (visas) PDFs, what counts as
the "right" price when multiple appear, and which patterns the parser
deliberately avoids.

The parser is consumed by:

- `src/ingestion/amf/bdif_poller.py` on live ingest (production pipeline),
- `scripts/backfill_p92_02a.py` and the audit scripts under `scripts/` for
  historical re-parses,
- the test suite under `tests/ingestion/amf/`.

---

## 1. Conventions

### 1.1 Dividend handling — cum-dividende

When an AMF filing mentions both a cum-dividende price and an ex-dividende
price (typical of any offer whose opening straddles a coupon detachment),
the parser stores the **cum-dividende** price — the announced offer price
before any dividend detachment.

Concrete corpus examples:

| Ref | Target | Stored (cum-div) | Not stored (ex-div) |
|---|---|---|---|
| 218C2043 | SELECTIRENTE | 89 € (`dividende attaché`) | 86.80 € (after detachment) |
| 219C0051 | TESSI | 160 € | 117.30 € |
| 220C4135 | LE BELIER | 38.18 € | 35.12 € |
| 225C1227 | GROUPE ETPO | 82.33 € (`dividende attaché`) | 71 € (`dividende détaché`) |

Rationale:

- **Reference value for M&A arbitrage.** The cum-div price is the headline
  number quoted in the offer and used by every counterparty before
  detachment.
- **Cross-deal consistency.** Most offers don't straddle a coupon
  detachment at all — for them, the cum-div price IS the price. Picking
  ex-div on the subset that does straddle would break dataset
  homogeneity.
- **Downstream concern.** A dividend-adjustment feature can apply the
  delta in a Phase 6 feature column if/when net-yield analytics become a
  requirement — the cum-div column stays the source of truth.

Implementation is implicit: the canonical AMF engagement clause
("`s'engage à acquérir au prix de X € (dividende attaché)`") quotes the
cum-div price first, so the engagement-clause anchor naturally picks
the cum-div value without an explicit dividend-aware branch.

### 1.2 Currency — EUR

AMF filings are always denominated in euros for the purpose of
`offer_price`. The parser keeps the `currency` field for future-proofing
(`CHF` / `GBP` / `USD` are recognised by the legacy first-match regex
should the corpus ever extend beyond the EU) but always returns `EUR`
when the price comes from the engagement-clause or surenchère anchors.

### 1.3 Source labels — `OfferPriceSource` enum

The parser tags every extraction with one of seven values from the
`OfferPriceSource(str, Enum)` enum in `src/ingestion/amf/parser.py`.
Stamped on `ParsedMetadata.extraction_source` and consumed by audit
scripts; not persisted on the `deals` table (kept process-side for the
moment).

| Label | Meaning |
|---|---|
| `engagement_clause_multi_bullet` | Reserved for a multi-bullet variant of the engagement clause. Currently subsumed by `engagement_clause` (the lazy span in `_ENGAGEMENT_CLAUSE` already crosses bullets). |
| `engagement_clause` | Primary anchor — `s'engage à acquérir … au prix [unitaire] de X €`. Strongest signal. |
| `surenchere_raised` | Pure surenchère filings without the engagement verb (`rehaussé/relevé/modifié/visées dorénavant`). |
| `dividend_cum_anchored` | Reserved for an explicit cum-div anchor. Not needed on the 02b corpus — the engagement clause already quotes the cum-div price. |
| `fallback_last_match` | Reserved for a "skip transparency noise then take the last match" fallback. Not needed on the 02b corpus. |
| `fallback_first_match` | Legacy P9.2 02a path. First `X €` match in the text, skipping anything preceded within 80 chars by a nominal-value marker (P9.1a BaFin guard, ported in 02a for SELECTIRENTE-class OCEANE par values). |
| `no_match` | No euro amount in the text. |

Three labels (`engagement_clause_multi_bullet`, `dividend_cum_anchored`,
`fallback_last_match`) are declared in the enum but unused — they are
kept reserved for future anchors should a new pattern emerge that the
current strategy doesn't cover.

---

## 2. Extraction priority order

`_extract_offer_price(text)` returns the first hit from a top-down
strategy:

| # | Source label | Trigger |
|---|---|---|
| 1 | `engagement_clause` | `s'engage à acquérir … au prix … de X €` (any French verb conjugation, lazy 400-char span between `acquérir` and the price). |
| 2 | `surenchere_raised` | `rehaussé / relevé / modifié / "visées dorénavant"` keyword followed within 100 chars by `au prix … de X €`. |
| 3 | `fallback_first_match` | Legacy first `X €` match with the P9.1a nominal-value 80-char guard. |
| 4 | `no_match` | No euro amount in the text. |

Order matters:

- **Engagement clause first** so any PDF that restates the offer
  commitment wins, including surenchère filings that include both the
  engagement verb and a `prix modifié/relevé` qualifier
  (CFI 218C1043, TRAVEL TECHNOLOGY INTERACTIVE 224C0915, NHOA 224C2193).
  On those, step 2 never fires.
- **Surenchère second** for pure-surenchère filings that don't restate
  the engagement verb (MEDIA 6 226C0661 / 226C0645 quote
  `prix d'offre libellé initialement au prix de 9,69 € était rehaussé
  au prix de 9,89 €` with no `s'engage`).
- **Fallback last** because the legacy first-match path can pick up
  transparency operations and block-trade recaps that appear before the
  engagement clause on retraits obligatoires. Reserved for filings whose
  formulation neither anchor recognises (rare on the current corpus).

The `engagement_clause` lazy span is hard-capped at **400 chars**
between `acquérir` and the price. This caps backtracking and matches
AMF's actual writing style — parenthetical inserts and bullet-list
sub-clauses fit under 400 chars on every observed sample.

---

## 3. Patterns deliberately avoided

The parser does not extract the prices that fall in these patterns —
the engagement-clause + surenchère anchors filter them out structurally
rather than via dedicated exclusions.

### 3.1 Block-trade transparency recaps

Retraits obligatoires and surenchères routinely recap the history of the
initiator's prior block acquisitions before stating the new offer price:

- *"L'initiateur a acquis, le 4 juin 2024, 712 493 actions TIPIAK … au
  prix unitaire de 82 €"* — recap of the trigger transaction
- *"le prix par action SERMA GROUP ressortant par transparence des
  opérations intervenues, le 12 septembre 2018, est de 229,19 €"* —
  reference operation
- *"acquisition d'actions GALIMMO par Carmila (au prix … de 9,02 €
  par action GALIMMO)"* — pre-OPAS block trade

These prices are NOT the offer price. The engagement-clause anchor
ignores them because it requires the forward verb `s'engage[r] à
acquérir` — recap text uses past-tense `a acquis` instead. The next
match for the canonical formulation (further down the PDF) wins.

### 3.2 OCEANE / BSA / warrant exercise prices

PDFs visa offers that carry secondary instruments (OCEANE convertibles,
BSAR warrants) quote their **exercise / strike price** alongside the
share offer price:

- TECHNICOLOR CREATIVE STUDIOS 223C2035: 0.01 € (BSA strike) vs 1.63 €
  (share offer price)
- TERACT 226C0550: 0.0039 € (BSAR price) + 11.50 € (BSAR exercise into
  share) vs 3.12 € (share offer price)

The engagement-clause anchor extracts the share offer price because
the share commitment is the one phrased
`s'engage à acquérir … au prix de X €`. BSAR/OCEANE leg prices appear in
separate sentences without that verb, or in bullet-list legs that the
lazy span happens to skip past.

The nominal-value guard from P9.1a (BaFin Grundkapital, ported in 02a
for SELECTIRENTE) also filters the `valeur nominale unitaire de X €`
case, which is a structurally similar trap.

### 3.3 Multi-bullet enumerations

AMF templates sometimes lay out multi-leg offers as a bulleted list:

```
L'initiateur s'engage irrévocablement à acquérir au prix de :
- 3,12 € par action TERACT
- 0,0039 € par BSAR B
```

The `engagement_clause` regex lazy span `[\s\S]{0,400}?` crosses the
colon + newline + dash and lands on the first bullet's amount (the
target's share price), which is what we want. The remaining bullets
(secondary instruments) are ignored.

Verified on TERACT 226C0550 + 226C0157.

### 3.4 Earlier / amended-away prices

Surenchère filings restate both the OLD and the NEW prices:

- *"prix unitaire relevé de 2,85 € (contre 2,34 € initialement
  annoncé)"* — TRAVEL TECH 224C0915
- *"au prix unitaire de 1,25 € au lieu de 1,10 €"* — NHOA 224C2193
- *"prix d'offre libellé initialement au prix de 9,69 € … était
  rehaussé au prix de 9,89 €"* — MEDIA 6 226C0661

The engagement-clause anchor naturally picks the NEW price when the
verb sits right next to it (TRAVEL TECH, NHOA 224C2193). The pure
surenchère anchor handles the no-verb case (MEDIA 6) by requiring the
surenchère keyword to precede an `au prix … de X €` consumer — the
keyword is always tied to the raised price, never to the original.

---

## 4. Phase 9.2 history

### 4.1 Step 0 audit (P9.2 02b)

- **Sample**: 68 deals stratified across 2022–2026 (60 random + 8
  obligatoires + known FPs from 02a closure)
- **Refined FP rate**: 15.0 % (9 confirmed FPs on the 60 random) — vs.
  20 % brut auto-classification.
- **Patterns**: 4 traps initially identified (BLOCK_PURCHASE,
  DIVIDEND_TRAP, SURENCHERE, OCEANE/BSA). All four resolved by the
  Step 1 fix below.
- **Extrapolation**: ~90 deals concerned on the 596 verified_cash
  population (interval ~75–105 at ±2σ).

See `docs/phase-09/p92_02b_step0_audit.md` for the full audit + the
list of 14 FPs and 3 false alarms catalogued.

### 4.2 Step 1 implementation (P9.2 02b)

| Sub-step | Commit | Outcome |
|---|---|---|
| 1a | `8ddf081 test(p92-02b): regression fixtures (failing red)` | 17 fixtures pinned (14 FP red + 3 false alarms green). |
| 1b | `e2e66a2 feat(p92-02b): fix BLOCK_PURCHASE via engagement clause anchoring + OfferPriceSource enum` | Engagement-clause anchor → 12 reds flip green. Subsumes BLOCK_PURCHASE + most DIVIDEND_TRAP + most OCEANE/BSA on the corpus. |
| 1c | `a9240cb feat(p92-02b): fix SURENCHERE pattern for amended prices (rehaussé/relevé/modifié)` | Surenchère anchor → remaining 2 MEDIA 6 reds flip green. **17/17 green.** |
| 1d/1e/1f | — | **Skipped as redundant.** Every DIVIDEND_TRAP / OCEANE_BSA / multi-bullet case in the corpus carried a clean engagement clause that step 1b picked up correctly; adding separate anchors would have added surface area for false positives without changing the outcome. |
| 1g | (this doc) | `docs(p92-02b): document AMF parser conventions and extraction priority`. |
| 1h | TBD | Re-run parser on the 596 verified_cash AMF deals + comparison report. **STOP-checkpoint before DB update.** |
| 1i | TBD | DB update of corrected prices (after user validates the 1h report). |
| 1j | TBD | Re-train Phase 6 scoring V1.1 on the cleaned dataset. |

Regression test fixtures live at
`tests/ingestion/amf/test_anchoring_fixtures_p92_02b.py` with text
excerpts under `tests/fixtures/p92_02b/` (mirror of the P9.1a BaFin +
P9.2 02a convention: tracked excerpts, gitignored PDFs).

---

## 5. Known limitations

- **PyMuPDF dependence.** Extraction quality follows PyMuPDF text
  output. Some legacy PDFs (pre-2016) with non-standard glyph mappings
  produce text where `'`, `à`, `é` are mis-decoded. The regex accepts
  ASCII apostrophe + curly U+2019 + accented and bare vowels (`[àa]`,
  `[ée]`) to compensate, but a heavily-mangled OCR fallback PDF will
  still degrade. Out of scope for P9.2 02b; revisit if 02f OCR work
  triggers it.
- **Cash offers only.** This document covers cash AMF offers — the
  engagement-clause anchor assumes `au prix de X €`. Share-exchange
  offers (OPE) without a cash leg are stored as `suspect_low_unverified`
  by the live service and are out of `verified_cash` scope. P10+ tech
  debt: structure cash + share legs as `ConsiderationStructured` (the
  pattern already exists on BaFin per P9.1c).
- **Verb coverage.** The engagement-clause regex matches `engage\w{0,6}`
  to cover French conjugations (présent, imparfait, futur, conditionnel,
  pluriel) without alternation order pitfalls (an earlier
  `(?:e|ait|ent|...)?` variant failed on `engageait` because the `e`
  alternative consumed before `ait` could fire). The 6-char trailing
  window is wide enough for every form observed in the corpus.

---

## 6. Touching this parser

1. **Read this doc + the Step 0 audit** at
   `docs/phase-09/p92_02b_step0_audit.md` before changing the regex
   strategy.
2. **Add a fixture first** for any new pattern under
   `tests/fixtures/p92_02b/<ref>_excerpt.txt` and a parametrized entry
   in `tests/ingestion/amf/test_anchoring_fixtures_p92_02b.py`.
3. **Run the full repo test suite** — every parser change must keep
   `pytest tests/` green.
4. **Re-run the audit** with `scripts/p92_02b_re_run_parser.py` (Step 1h
   tool) on the 596 verified_cash deals before any DB update to surface
   unintended regressions on the historical corpus.
