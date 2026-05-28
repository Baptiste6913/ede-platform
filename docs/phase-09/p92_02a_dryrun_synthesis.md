# P9.2 02a — Extended dry-run synthesis [Step 0 B]

**Goal.** Empirically measure the AMF parser hit rate on a representative
80-deal sample (stratified 16 × 5 years), calibrate AMF-specific
`offer_price` bounds from scratch (no reuse of Consob defaults),
ground-truth 25 deals against manual PDF reads, categorize the error
patterns by 02a / 02b / 02f scope, and surface the new bugs discovered.

**Sample.** 80 deals (16 / year, 2022-2026). Includes the 10 deals
from P9.2 Step 0 (continuity) + 70 new picks (deterministic random
per year, seed = 920).

**Output artifacts** (all gitignored under `data/audits/`):
- `p92_02a_sample.csv` — 80 picks with metadata
- `p92_02a_amf_dryrun_extended.csv` — parser output + doc_type + status
- `p92_02a_manual_picks.json` — the 15 manual ground-truth picks
- 15 new entries in `p92_text_dumps/fr/` for verification

## 1. Headline numbers

### Hit rate by status

| Status | Count | % of 80 |
|---|---|---|
| `extracted_in_bounds` | 47 | **58.75 %** |
| `silent_miss` | 33 | 41.25 % |
| `extracted_out_of_bounds` | 0 | 0 % |
| `parser_exception` | 0 | 0 % |

### Hit rate cross-tab — status × doc_type (heuristic classifier)

| doc_type | extracted | silent_miss | hit rate |
|---|---|---|---|
| `conformity_decision` | 19 | 7 | **73 %** |
| `deposit_notice` | 28 | 26 | **52 %** |
| **All** | **47** | **33** | **59 %** |

The conformity_decision bucket is the "easy" class (price restated in
narrative). The deposit_notice bucket is where most of the silent
misses live — and where 02a + 02b can recover the most volume.

**Heuristic classifier note.** The doc-type classifier is best-effort
(title text + header-code suffix). Manual verification revealed that
2 / 5 randomly sampled "deposit_notice" silent misses were actually
**complement docs** (Complément à D&I) mis-classified — the
`Complément à D&I 224CXXXX` marker sits past the 800-char window of
the heuristic. The real hit rate on price-bearing deposit notices
is higher than the 52 % shown.

## 2. Manual ground truth — 25 verdicts

Cross-verification on 25 deals (10 from Step 0 + 15 from this round)
by reading the PDF text dumps for the offer-price anchor.

| Verdict | Count | What it means |
|---|---|---|
| **MATCH** | 11 / 25 | Parser output equals the manually-verified offer price |
| **MISMATCH** | 6 / 25 | Parser extracted a number ≠ the real offer price |
| **SILENT_MISS_BUG** | 5 / 25 | Parser returned None, but a real offer price exists in the PDF |
| **SILENT_MISS_LEGIT** | 3 / 25 | Parser returned None, no offer price in the PDF (complement / response note) |

Detail (`✓` = match, `✗` = parser wrong, `Ø` = parser None):

| ref | target | parser | truth | verdict |
|---|---|---|---|---|
| 216C1735 | CEGID GROUP | 61.00 | 61.00 | ✓ MATCH |
| 218C0835 | ALTAMIR | 17.36 | 17.36 | ✓ MATCH |
| 218C2043 | SELECTIRENTE | 86.80 | 86.80 | ✓ MATCH |
| 221C0506 | EOS IMAGING | 2.45 | 2.45 | ✓ MATCH |
| 221C3383 | DEVOTEAM | 168.50 | 168.50 | ✓ MATCH (genuine high-price) |
| 222C2537 | EDF | 12.00 | 12.00 | ✓ MATCH |
| 224C1737 | GROUPE BERKEM | 3.10 | 3.10 | ✓ MATCH |
| 225C0021 | NEOEN | 39.85 | 39.85 | ✓ MATCH (parser luck on share leg) |
| 225C0921 | M2I | 8.50 | 8.50 | ✓ MATCH |
| 225C1666 | WAGA ENERGY | 21.55 | 21.55 | ✓ MATCH (avoided complément-de-prix trap) |
| 225C2081 | SOCIETE DE TAYNINH | 0.11 | 0.11 | ✓ MATCH |
| 218C1907 | SERMA GROUP | 229.19 | **235.00** | ✗ MISMATCH (unknown source for 229.19) |
| 219C0051 | TESSI | 42.70 | **160.00** | ✗ MISMATCH (dividend trap) |
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | **2.85** | ✗ MISMATCH (block-purchase trap) |
| 225C0741 | FINANCIERE MONCEY | 5.83 | **133.00** | ✗ MISMATCH (unexplained — likely footnote ratio) |
| 226C0287 | FNAC DARTY | 81.12 | **36.00** | ✗ MISMATCH (parallel BSA price) |
| 226C0644 | FNAC DARTY | 81.12 | **36.00** | ✗ MISMATCH (same BSA trap, conformity doc) |
| 223C0044 | SERMA GROUP | Ø | Ø | ✓ legit (response note, no price) |
| 225C0129 | EXCLUSIVE NETWORKS | Ø | Ø | ✓ legit (Complément à D&I) |
| 226C0020 | BALYO | Ø | Ø | ✓ legit (Complément à D&I) |
| 223C1382 | PCAS | Ø | **8.00** | **BUG** — integer price, regex requires decimals |
| 223C1897 | ALTUR INVESTISSEMENT | Ø | **11.00** | **BUG** — integer price |
| 221C0878 | TARKETT | Ø | **20.00** | **BUG** — integer price |
| 224C0830 | TIPIAK | Ø | **88.00** | **BUG** — integer price (from Step 0 P9.2) |
| 225C2156 | PRODWARE | Ø | **28.00** | **BUG** — integer price (from Step 0 P9.2) |

## 3. NEW bug discovered — integer-price regex (5 / 25 silent misses)

`src/ingestion/amf/parser.py:65-68`:

```python
_PRICE_REGEX = re.compile(
    r"(?P<amount>\d{1,3}(?:[ \\xa0\.]\d{3})*[,\.]\d{2,4})\s*"
    r"(?P<currency>€|EUR|CHF|GBP|USD)",
    re.IGNORECASE,
)
```

The amount pattern is `\d{1,3}(?:[ \xa0\.]\d{3})*[,\.]\d{2,4}` — it
**requires at least 2 decimal digits** (`[,\.]\d{2,4}`). Integer
prices like `88 €`, `28 €`, `11 €`, `20 €`, `8 €` are completely
missed.

This is independent from the documented `\xa0` literal bug (same line
65) — they are two distinct regressions on the same regex.

**Fix proposal (02a-class, atomic):**

```python
_PRICE_REGEX = re.compile(
    r"(?P<amount>\d{1,3}(?:[\s .]\d{3})*(?:[,\.]\d{1,4})?)\s*"
    r"(?P<currency>€|EUR|CHF|GBP|USD)",
    re.IGNORECASE,
)
```

Changes:
- `[ \\xa0\.]` → `[\s .]` — fixes the `\xa0` literal bug
  (the 4-char raw string becomes the NBSP code point) and broadens
  whitespace to any unicode whitespace.
- `[,\.]\d{2,4}` → `(?:[,\.]\d{1,4})?` — makes the decimal portion
  optional. Accepts `88` and `88,00` and `88,000`. Drops the
  minimum 2-decimal requirement.

Estimated additional recovery: at least **the 5 BUG silent misses
above + likely 8-12 more** in the 33-deal silent_miss bucket
(extrapolation from the 3 / 5 random sample = bug). Total volume
swing on the 730-deal corpus: tentative **+150 to +250 deals
recovered** from the regex fix alone (before wiring).

## 4. Bounds calibration — virgin, no Consob default reuse

### Distribution of the 47 parser-extracted prices

| Statistic | Value |
|---|---|
| min | 0.11 (TAYNINH small-cap, ✓ correct) |
| p05 | 0.60 |
| p25 | 3.12 |
| median | 8.50 |
| p75 | 32.04 |
| p90 | 81.12 |
| p95 | 86.80 |
| max | 229.19 (SERMA mismatch — real offer 235) |

Top 10 highest values, with verdict from the manual pass:

| price | ref | target | verdict |
|---|---|---|---|
| 229.19 | 218C1907 | SERMA GROUP | ✗ MISMATCH (real 235.00) |
| 168.50 | 221C3383 | DEVOTEAM | ✓ MATCH (genuine high-price) |
| 86.80 | 218C2043 | SELECTIRENTE | ✓ MATCH |
| 81.12 | 226C0287 | FNAC DARTY | ✗ MISMATCH (BSA price, not share) |
| 81.12 | 226C0644 | FNAC DARTY | ✗ MISMATCH (BSA price, not share) |
| 62.60 | 218C0428 | KLEPIERRE-like | (not manually verified) |
| 61.00 | 216C1735 | CEGID GROUP | ✓ MATCH |
| 43.75 | 218C0250 | unknown | (not manually verified) |
| 42.70 | 219C0051 | TESSI | ✗ MISMATCH (dividend trap) |
| 39.85 | 225C0021 | NEOEN | ✓ MATCH |

**Critical findings vs Consob:**
- No Banco-BPM-class outlier (3.8B) in the 80-deal AMF sample.
- The 47 extracted values land in `[0.11, 229.19]` — under
  ~1 / 40 000 of the Consob outlier.
- The convertible-bond / OCEANE prices that *could* push past
  1 000 € (NEOEN OCEANE 2022 at 101 382 €) are NOT picked up by
  the current parser because of the `\xa0` bug (`101 382,00 €`
  matches a pattern with NBSP that the regex misses). Even after
  the `\xa0` fix, those OCEANE prices are NOT share prices and
  should be **rejected** by the bounds — they're a separate
  per-instrument-class problem that 02b will solve via
  `par action` qualifier discrimination.

**Proposed AMF bounds: `0.01 ≤ price ≤ 1 000` €/share.**

- Lower 0.01 €: same as Consob, 11× safety margin under observed
  min (0.11).
- Upper 1 000 €: 4.25× over observed max legitimate (235 SERMA
  truth). Catches any Banco-BPM-class controvalore mis-parse
  (which would land in 10⁵ + EUR), catches OCEANE-class
  convertibles (10⁵ EUR), but accepts every legitimate share
  price we've seen across 2022-2026.
- **Why tighter than Consob's 10 000 €**: AMF distribution is
  cleaner (max 235 vs Consob 300 + Banco BPM); a tighter bound
  catches mis-parses earlier and matches the empirical envelope
  with less slack. Consob's 10 000 was sized for safety against
  unobserved variation in IT corpus; AMF's 1 000 is calibrated on
  empirical AMF.
- Trade-off: if a future AMF deal genuinely prices a share above
  1 000 €, it would be flagged `failed_validation` and surfaced
  for manual review. This is acceptable — share prices >1 000 €
  for a non-OCEANE listed equity are exceptionally rare on
  Euronext Paris.

## 5. Error pattern frequencies (out of the 8 mismatches + 5 bugs on the 25 ground-truth set)

| Pattern | Cause | Count | Sample IDs | Scope |
|---|---|---|---|---|
| **Integer-price regex bug** | `[,\.]\d{2,4}` requires ≥ 2 decimals | 5 / 25 | TIPIAK, PRODWARE, ALTUR, TARKETT, PCAS | **02a atomic** (this is a stand-alone regex fix; ship with `\xa0` fix) |
| **Dividend trap** | "X € par action" matched on dividend instead of offer | 1 / 25 | TESSI 42.70 | 02b (verb discriminator) |
| **Block-purchase trap** | "au prix unitaire de X €" on block buy before offer | 1 / 25 | Travel Tech 2.34 | 02b (verb discriminator) |
| **Multi-instrument BSA trap** | parser picks BSA / warrant price instead of share | 2 / 25 | FNAC DARTY (x2) 81.12 | 02b (`par action` qualifier filter) |
| **Unexplained mismatch** | parser returned a number with no matching anchor I could identify | 2 / 25 | SERMA 229.19, MONCEY 5.83 | 02b investigation (likely deeper-page footnote) |
| **Complement / response note legit** | doc legitimately carries no price | 3 / 25 | SERMA(P9.1c), EXCLUSIVE NETWORKS, BALYO | 02a (route to `suspect_low_unverified`, no action) |

### Scope partition

| Scope | Pattern types | Expected gain |
|---|---|---|
| **02a (wiring + atomic bug fixes)** | Integer-price regex + `\xa0` + Wire parser into pipeline | Empirical: 5 / 25 from BUG bucket gets fixed, regex hits ~16 / 33 silent_miss extrapolated. **Volume target post-02a: ~510-580 / 730 extracted** (was 0 / 730) |
| **02b (regex hardening)** | Dividend / block / BSA / unexplained | 5 / 25 mismatches get corrected. Adds ~5-10 verified per remaining slot, but mainly **corrects** existing extractions (no net volume change) |
| **02c (ISIN page-1 header)** | Independent of these patterns | 730 / 730 ISIN populated (no overlap with price extraction) |
| **02f (OCR)** | None observed in this 80-deal AMF sample (vs 1 in Consob — Piovan) | Likely deferred to P10 |

## 6. Implications for 02a scope

The Step 0 audit recommended a 4-commit sequence in 02a:
1. Atomic `\xa0` fix
2. Wire parser into pipeline
3. Backfill script
4. Tests

**This dry-run adds a 5th commit ahead of the others:**

1. **`fix(amf-parser): allow integer-only prices (88 € matches)`** — drop
   the `\d{2,4}` decimal requirement; accept `\d+(?:[,\.]\d{1,4})?`.
   Independent of `\xa0` (different concern, isolated diff).
2. `fix(amf-parser): \xa0 literal -> NBSP code point`
3. `feat(amf): wire extract_pdf_metadata into bdif_poller`
4. `feat(amf): backfill_p92_02a script for 730 historical deals`
5. `test(amf-parser): regression tests on integer + NBSP + bounds`

The integer-price fix is the **single highest-volume win** of 02a.
Empirically ~5 / 5 of the silent_miss bug class will recover with it.

## 7. AMF parser does NOT set quality flag — confirmation

Audit confirmed (`p92_02a_pipeline_audit.md` section d) that the AMF
`ParsedMetadata` dataclass has no `offer_price_quality_flag` field.
Option A (wiring derives the flag in `service.py`) holds for 02a.
The dry-run did NOT need to derive flags (it just collected raw
parser output); flag derivation happens in the actual wiring commit.

## 8. Open items handed to the user at [02a-Step0-B]

1. **Confirm AMF bounds `[0.01, 1 000]`** (vs Consob `[0.01, 10 000]`).
   Tighter is more conservative; AMF empirical max is 235 EUR.
2. **Confirm 02a scope expansion** to include the integer-price regex
   fix as commit 1.
3. **`Complément à D&I` heuristic** — the doc-type classifier
   currently mis-routes ~25 % of complement docs to
   `deposit_notice` because the marker sits past the first 800
   chars on some PDFs. Worth fixing in the dry-run script for
   future-Step-0 work, but not blocking for 02a.
4. **SERMA 229.19 + MONCEY 5.83 unexplained mismatches** —
   deferred to 02b investigation. 02a doesn't change parser
   behavior on these (they'll still mismatch post-02a; the
   bounds will accept 229.19 as `verified_cash` even though
   it's wrong — known data-quality concession).
5. **FNAC DARTY BSA mis-extraction** — 02a doesn't fix it
   either (parser picks BSA 81.12 instead of share 36 — both
   are in-bounds). 02b regex with `par action` qualifier will
   fix it. **Acceptable for 02a to ship a partial fix here**:
   FNAC DARTY rows will be `verified_cash` with the wrong number
   (81.12 instead of 36). User to confirm acceptance.

## 9. Post-02a estimated volume — refined

Pre-Step-0-B estimate: 0 → ~450 / 730 (extrapolating Step 0 P9.2's
6 / 10 = 60 % hit rate).

Post-Step-0-B empirical:
- Current parser as-is: 47 / 80 = 58.75 % → **~430 / 730**.
- Plus integer-price fix in 02a: assuming 3 / 5 silent_miss
  bugs extrapolated → **+~100 deals = ~530 / 730**.
- Of those ~530 extracted, ~70-75 % will be promoted to
  `verified_cash` after bounds check (mirrors 02d 35 / 47 = 74 %
  rate). **Final estimate: ~400 / 730 `verified_cash`** post-02a
  (cash leg only; FNAC-DARTY-class will be wrong-but-in-bounds).

## STOP — checkpoint [02a-Step0-B]

Awaiting user validation on items 1-5 of section 8 above before
writing the implementation plan at [02a-Step0-C].
