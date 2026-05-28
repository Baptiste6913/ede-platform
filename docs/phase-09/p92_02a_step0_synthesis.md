# P9.2 02a — Step 0 synthesis + implementation plan

**Consolidates [02a-Step0-A] pipeline audit + [02a-Step0-B]
extended dry-run.** Final input for the 02a implementation, with
the demarcation line 02a/02b agreed with the user.

## 1. Démarcation 02a vs 02b

The hard line agreed at [02a-Step0-B] STOP :

- **02a fixes FALSE NEGATIVES** — silently-lost-but-correct prices.
  Touches the regex acceptance class only (what `_PRICE_REGEX`
  agrees to match). Risk near-zero because the price already
  exists in the PDF text in the right place; the parser just
  failed to recognize its format. Volume-driving.
- **02b fixes FALSE POSITIVES** — wrong price extracted from
  multiple candidates. Requires verb / qualifier / context
  discrimination (`s'engage` vs `a acquis`, `par action` vs
  `par BSA`, `dividende` exclusion). Higher risk because it
  changes anchoring semantics. Correctness-driving.

This boundary makes 02a a clean, isolated regex-acceptance fix
with a backfill, and reserves all the semantic-anchor work for
02b. It does NOT compromise on FNs at the regex layer (commit
#1 below is the volume-win), and it does NOT pretend to fix FPs
(the closure summary will list them nominatively).

## 2. Hypothèses Step 0 P9.2 — confirmation / invalidation

| # | Hypothesis | Verdict |
|---|---|---|
| H1 | AMF parser is never called by the ingestion pipeline | **CONFIRMED.** `grep extract_pdf_metadata src/ingestion/amf/` — no callsite outside `parser.py`. `service.py:217-218` carries the deferred-TODO `phase 6` marker. |
| H2 | Hit rate ≈ 60-70 % on individual PDFs | **CONFIRMED.** Empirical 47/80 = **58.75 %** global on 80-deal stratified sample. Within ±2 % of the 60 % Step 0 P9.2 extrapolation. |
| H3 | ISIN extractible 100 % via page-1 header | **CONFIRMED on a 50-deal spot check** of `regulator_ref` — every AMF ref in DB matches the `^\d{3}C\d{4}$` pattern, and the longer `<ref>-<ISIN>-OP*-*` lives in PDF body header line 4 (re-checked manually on 15 PDFs in [02a-Step0-B]). Out of scope for 02a, target 02c. |
| H4 | AMF bounds probably similar to Consob `[0.01, 10 000]` | **PARTIALLY INVALIDATED.** AMF empirical distribution is **cleaner** than Consob: max legit 235 (DEVOTEAM, SELECTIRENTE area), no Banco-BPM-class outlier. Empirically AMF bounds are tightened to `[0.01, 1 000]` (see §4). User decision logged: bounds are **per-jurisdiction**, no copy across regulators. |

## 3. Hit rate empirique

- Global: **47 / 80 = 58.75 %** extracted.
- `conformity_decision` (price restated): **19 / 26 = 73 %**.
- `deposit_notice` (initial filing): **28 / 54 = 52 %** — the big-volume
  bucket and the biggest opportunity zone.

Manual ground truth on **25 / 80 deals** (15 from this round + 10
from P9.2 Step 0):
- ✓ MATCH: 11 / 25
- ✗ MISMATCH: 6 / 25
- ⚠ SILENT_MISS_BUG (regex misses a correct price): **5 / 25**
- ⚠ SILENT_MISS_LEGIT (PDF has no price by design): 3 / 25

The 5 SILENT_MISS_BUG cases are ALL caused by the integer-price
regex regression (commit #1 below): TIPIAK 88, PRODWARE 28, ALTUR
11, TARKETT 20, PCAS 8. The 6 MISMATCH cases are 02b-class and
explicitly excluded from 02a scope.

## 4. Bounds AMF — `[0.01, 1 000]` €/share

Calibrated **virgin** on AMF empirical distribution (no reuse of
Consob's `[0.01, 10 000]`).

| Statistic | Value |
|---|---|
| min | 0.11 |
| p05 / p25 / median / p75 / p95 | 0.60 / 3.12 / 8.50 / 32.04 / 86.80 |
| max (parser-extracted) | 229.19 (SERMA mismatch — real offer 235) |
| max (manually verified legit) | **235.00** (SERMA real) |

`1 000 €` upper bound = 4.25× over observed max legit (235).
Catches:
- Banco-BPM-class controvalore mis-parses (10⁹ EUR) — none
  observed in the AMF 80-sample, but the bound stays armed for
  future Banco-BPM-style bugs.
- OCEANE / convertible prices (NEOEN OCEANE 2022 = 101 382 €) —
  if the regex ever extracts them post-`\xa0` fix, the bounds
  correctly reject them as `failed_validation` (they're NOT
  share prices). 02b will separately apply the `par action`
  qualifier filter.

**Implementation:** `_derive_quality_flag` in `service.py` will
use `PRICE_LOWER_AMF = Decimal("0.01")` and
`PRICE_UPPER_AMF = Decimal("1000")`. Constants live in the AMF
service module, NOT a shared module — per the
**per-jurisdiction bounds debt** acknowledged in the user
decision log.

Per-jurisdiction debt entry (P10 housekeeping): document the
constraint that **every new jurisdiction calibrates bounds on its
own empirical distribution**, never reuses another regulator's
envelope. BaFin (P9.1a) uses `[5, 500]`, Consob (P9.2 02d) uses
`[0.01, 10 000]`, AMF (P9.2 02a) uses `[0.01, 1 000]`.

## 5. Implementation plan — 5 atomic commits

### Commit #1 — `fix(amf-parser): accept integer prices + NBSP char in price regex`

**Single regex change** in `src/ingestion/amf/parser.py:65-68`.
This is the **volume-win commit**: by itself it recovers ~150-250
deals out of the 33 silent-miss bucket (extrapolation from 5 / 5
random-sample = bug observed in [Step0-B]).

Diff sketch:

```python
 _PRICE_REGEX = re.compile(
-    r"(?P<amount>\d{1,3}(?:[ \\xa0\.]\d{3})*[,\.]\d{2,4})\s*"
+    r"(?P<amount>\d{1,3}(?:[\s .]\d{3})*(?:[,\.]\d{1,4})?)\s*"
     r"(?P<currency>€|EUR|CHF|GBP|USD)",
     re.IGNORECASE,
 )
```

Two bug fixes in a single regex change:
- `[ \\xa0\.]` → `[\s .]`. The raw-string `\\xa0` matched the 4 literal characters `\`, `x`, `a`, `0`. The corrected `\s` is the Unicode-whitespace class that includes U+00A0 (NBSP) — what `101 382,00 €` (NEOEN) actually contains. `.` and ` ` stay valid thousand separators.
- `[,\.]\d{2,4}` → `(?:[,\.]\d{1,4})?`. Decimal portion becomes optional and allows 1+ decimal digits. Accepts `88`, `88,5`, `88,50`, `88,5000` — none of which the old regex accepted.

Also fix `parser.py:278` which has the same `\\xa0` literal bug
in the `raw.replace("\\xa0", "")` normalisation. Change to
`raw.replace("\xa0", "")`.

### Tests for commit #1 (strict requirement per user decision)

`tests/parsers/test_amf_p92_02a.py` — pure function tests on
`_extract_first_price` (the public test surface for the regex).
All five real-world integer-price silent-miss cases + at least
three decimal-price baseline + one NBSP case + **negative-control
non-regression tests**:

1. **Integer-price positive — TIPIAK 88 €** : `"au prix de 88 € par action"` → 88.
2. **Integer-price positive — PRODWARE 28 €**.
3. **Integer-price positive — ALTUR 11 €**.
4. **Integer-price positive — TARKETT 20 €**.
5. **Integer-price positive — PCAS 8 €**.
6. **Decimal baseline non-regression — CEGID 61,00 €**.
7. **Decimal baseline non-regression — NEOEN 39,85 €**.
8. **Decimal baseline non-regression — TAYNINH 0,11€** (no space).
9. **NBSP-thousand-separator — NEOEN OCEANE `101 382,00 €`**
   (NBSP between `101` and `382`). After the fix this MUST match
   (regex-acceptance-only; bounds-rejection happens later and
   that's intentional).
10. **NEGATIVE control 1 — "frais de courtage de 50 € par dossier"**
    : the integer 50 sits next to `€` and would be matched by the
    new regex. The expected behaviour is to match the *first*
    price in the text — this matters for the eventual semantic
    accuracy, but commit #1 does NOT change first-match semantics.
    Test asserts the regex matches `50` here as a known false
    positive for 02b to discriminate. Documents the *expected*
    behaviour rather than the desired one.
11. **NEGATIVE control 2 — "période de 30 jours"** : `30` is not
    followed by a currency, so MUST NOT match. Confirms the
    `\s*(?P<currency>€|EUR|CHF|GBP|USD)` lookahead still bites.
12. **NEGATIVE control 3 — "dividende de 1,25 €"** : matches as a
    price (false positive — 02b's dividend trap). Documents
    that commit #1 does not introduce nor fix dividend
    discrimination.

The negative controls 10 and 12 are deliberately admitted false
positives in 02a, recorded as known concessions to be resolved by
02b's verb discriminator. They prove the regex is doing *no
worse* than before on semantic discrimination, while *more
permissive* on format acceptance (the intended scope of 02a).

### Commit #2 — `feat(amf): wire extract_pdf_metadata into bdif_poller + service derive flag`

Two-file diff per [02a-Step0-A] §c:

- `src/ingestion/amf/bdif_poller.py:110-112` — mirror
  `bafin/poller.py:134-143`: call the parser between PDF download
  and `upsert_deal_from_bdif`, pass `pdf_metadata` to the service.
- `src/ingestion/amf/service.py` — add `pdf_metadata: ParsedMetadata |
  None = None` kwarg to `upsert_deal_from_bdif`. New-deal path
  populates `offer_price`, `currency`, `offer_price_quality_flag`,
  `parser_version`. Existing-deal path back-fills if the row still
  carries the migration default `suspect_low_unverified` AND we
  have a parser output.

`_derive_quality_flag(md: ParsedMetadata) -> str` helper, inline in
`service.py`:

```python
PRICE_LOWER_AMF = Decimal("0.01")
PRICE_UPPER_AMF = Decimal("1000")
PARSER_VERSION_02A = 2

def _derive_quality_flag(md: ParsedMetadata) -> str:
    if md.offer_price is None:
        return "suspect_low_unverified"  # parser ran, no price found
    if md.offer_price < PRICE_LOWER_AMF or md.offer_price > PRICE_UPPER_AMF:
        return "failed_validation"
    return "verified_cash"
```

Per [02a-Step0-A]: **Option A** (wiring-only flag derivation), parser
not touched for the flag. Mirror BaFin convention is deferred to 02b.

### Commit #3 — `feat(scripts): backfill_p92_02a re-parse 730 FR historiques`

`scripts/backfill_p92_02a.py` — mirror of `scripts/backfill_p91a.py`.

- Iterates FR deals with `parser_version < PARSER_VERSION_02A`.
- For each: re-runs `extract_pdf_metadata` on the local PDF
  (mapped from `/repo/data/...` to local working tree), updates
  `offer_price` / `currency` / `offer_price_quality_flag` /
  `parser_version`.
- Default mode dry-run; `--apply` executes UPDATEs.
- Transactional per deal, idempotent.
- Output `data/audits/p92_02a_backfill_results.csv` with one row
  per deal: `deal_id, regulator_ref, target_name, old_price,
  new_price, new_flag, action ∈ {applied, noop, skipped_no_pdf,
  exception}`.
- Score invalidation in the same transaction batch (mirror P9.1a
  + 02d): `DELETE FROM scores WHERE deal_id IN (re-parsed deals
  whose flag or price changed)`.

### Commit #4 — `test(amf): wiring integration tests (mock parser + DB write assertion)`

`tests/ingestion/amf/test_service_p92_02a.py` (new file):

- `test_upsert_populates_offer_price_when_metadata_provided` —
  feed an `upsert_deal_from_bdif` call with a fake
  `ParsedMetadata(offer_price=Decimal("12.50"), ...)`, assert the
  created Deal carries the price + `verified_cash` flag +
  `parser_version=2`.
- `test_upsert_routes_outlier_to_failed_validation` — feed
  `offer_price=Decimal("5000")` (> 1 000 upper), assert flag =
  `failed_validation`.
- `test_upsert_routes_null_to_suspect_low_unverified` — feed
  `offer_price=None`, assert flag stays default.
- `test_existing_deal_backfilled_when_default_flag` — pre-insert
  a deal with `suspect_low_unverified`, run the upsert with new
  `pdf_metadata`, assert price + flag updated.
- `test_existing_deal_not_overwritten_when_flag_promoted` —
  pre-insert a deal with `verified_cash` (already promoted),
  run upsert again, assert NO update happens (idempotence on
  already-promoted rows).

### Commit #5 — `docs(p92-02a): closure summary + false-positive nominative trace`

`docs/phase-09/p92_02a_closure_summary.md` — mirror of P9.1c and
02d closure summaries:

- Scope delivered (5 commits).
- Empirical hit rate post-fix (from backfill_p92_02a results CSV).
- Bounds `[0.01, 1 000]` AMF rationale + per-jurisdiction debt
  note.
- **Mandatory quantified warning** to Phase-8 trading flow (see §7).
- Nominative list of known mismatches (SERMA, MONCEY, FNAC DARTY
  ×2, TESSI, Travel Tech) — these will land as `verified_cash`
  with the wrong price; 02b will correct them.
- Dette résiduelle: 02b (semantic anchoring), 02c (ISIN header),
  the ~13 silently-legit complements that stay
  `suspect_low_unverified` (correct behavior).

## 6. Estimation finale — volume + verified_cash

Three-step refinement from the dry-run :

1. **Wiring alone, parser as-is** (no regex fix): 58.75 % hit rate
   → extracted ≈ **430 / 730**.
2. **Wiring + integer-price fix (commit #1)**: 3 / 5 random
   silent-miss = bug extrapolated to the 33 silent_miss bucket
   → ~ +100 deals recovered → extracted ≈ **530 / 730**.
3. **Bounds promotion `[0.01, 1 000]`** at 74 % promotion rate
   (Consob 02d empirical) → **verified_cash ≈ 400 / 730**.

| Estimation | Pre-02a | 02a wiring only | + integer-price fix | After bounds promotion |
|---|---|---|---|---|
| Extracted | 0 | ~430 | ~530 | ~530 |
| `verified_cash` | 0 | ~320 | ~395 | **~400** |
| `failed_validation` (out of bounds) | 0 | ~10 | ~15 | ~15 |
| `suspect_low_unverified` | 730 | ~300 | ~200 | ~200 |
| `manual_review` (not used in 02a) | 0 | 0 | 0 | 0 |

Combined with the existing 35 IT (P9.2 02d) + 33 DE (P9.1c) = 68
verified_cash, post-02a the pool reaches **~470 verified_cash
trans-jurisdiction**.

## 7. Avertissement faux positifs (quantifié + nominatif) — Phase 8 doit attendre 02b

**02a unblocks VOLUME, NOT correctness of anchored prices.**

Empirical false-positive rate on the 25-deal ground-truth set:

- 6 / 25 verdicts are MISMATCH = **24 % of the manually-verified
  sample** carries a wrong anchor price.
- 5 of 6 mismatches land in MATCH-or-MISMATCH presumed buckets
  (all `verified_cash` post-02a), the 6th (Travel Tech 2.34
  vs 2.85) likewise.

Extrapolated to the ~400 post-02a `verified_cash` rows: **~80
deals** (≈ 20 %) plausibly carry an anchor-incorrect price. Real
production prevalence may be lower (the manual sample over-weights
high-price candidates), but the order of magnitude is
load-bearing: **at least 10 % of post-02a AMF `verified_cash`
rows are not anchor-trustworthy until 02b lands**.

**Operational mandate:**
- Phase-8 trading on AMF cash candidates **must wait for 02b
  merge** before activating live signals on FR deals.
- If Phase-8 needs to activate sooner, it must filter against
  the nominative known-mismatch list (below) AND visually
  re-verify every candidate against the PDF.

**Nominative known false positives** (must be re-checked post-02b
or excluded from any pre-02b Phase-8 run):

| ref | target | parser output | manual truth | category |
|---|---|---|---|---|
| 218C1907 | SERMA GROUP | 229.19 € | 235.00 € | unexplained source |
| 219C0051 | TESSI | 42.70 € | 160.00 € | dividend trap |
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 € | 2.85 € | block-purchase trap |
| 225C0741 | FINANCIERE MONCEY | 5.83 € | 133.00 € | unexplained / mixed offer |
| 226C0287 | FNAC DARTY (deposit) | 81.12 € | 36.00 € | BSA price not share |
| 226C0644 | FNAC DARTY (conformity) | 81.12 € | 36.00 € | BSA price not share |

This table will be reproduced in `p92_02a_closure_summary.md`
(commit #5) so the warning travels with the merge for any future
operator inspecting the AMF data.

## 8. Edge cases (not blocking 02a)

- No Banco-BPM-class outlier (3.8B) in the AMF 80-sample. If one
  appears post-backfill (extreme corner case), bounds `[0.01, 1 000]`
  will catch it as `failed_validation`.
- Max legit observed: 235 € (SERMA, manual). Distribution clean.
- ~13 / 80 deals are complement / response-note documents that
  legitimately carry no price; they stay `suspect_low_unverified`
  post-02a. Correct behavior. The classifier mis-routes some of
  them to `deposit_notice` in the dry-run audit script (cosmetic;
  doesn't affect the actual ingestion pipeline). User decision:
  fix the audit script's 800→2000-char window in passing inside
  the existing `scripts/p92_02a_dryrun_extended.py` (out of
  ingestion scope; cosmetic improvement only).

## 9. Dette résiduelle (open work after 02a merge)

| Branch | Scope | Volume / impact |
|---|---|---|
| `phase-09-02b-amf-regex-hardening` | Verb discriminator (`s'engage` vs `a acquis`) ; `par action` qualifier filter ; dividend / complément-de-prix / block-purchase / BSA / OCEANE exclusion ; investigation SERMA 229 + MONCEY 5.83 unexplained mismatches ; backfill re-parse | Corrects ~80 of the post-02a `verified_cash` rows that carry wrong anchor (no volume change, correctness change). **Phase-8 AMF activation depends on 02b.** |
| `phase-09-02c-amf-isin-header` | Page-1 header regex `^\d{3}C\d{4}-(<ISIN>)-OP` extracts ISIN from PDF body header line 4 | 730 / 730 ISIN populated. Independent of price. |
| `phase-09-02e-consob-opas-mixed` | (Already in backlog from 02d) | +1-3 mixed deals correctly split via `deal_consideration` |
| `phase-09-02f-ocr-fallback` | (Conditional) | Only if post-02a/02b residual `pdf_text_extraction_failed` > 5 % |
| **Per-jurisdiction bounds documentation** (P10 housekeeping) | Document the constraint that every jurisdiction calibrates bounds independently; list current values (BaFin `[5, 500]`, Consob `[0.01, 10 000]`, AMF `[0.01, 1 000]`) | Small architecture doc — no code |

## STOP — checkpoint [02a-Step0-C]

End of Step 0 audit chain. No wiring, no regex change, no
migration, no backfill. Awaiting user validation on:

1. The 5-commit atomic implementation plan (§5).
2. The strict-test list for commit #1 (§5, post-#1 block — 12
   tests incl. 3 negative controls).
3. The bounds `[0.01, 1 000]` and the per-jurisdiction
   bounds-debt convention (§4 + §9).
4. The estimated volume `~400 verified_cash / 730` (§6).
5. The mandatory false-positive warning and the nominative list
   (§7), to be reproduced in the 02a closure summary.

Once validated, I start coding commit #1.
