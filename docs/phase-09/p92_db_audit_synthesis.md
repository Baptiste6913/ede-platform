# P9.2 Step 0 — DB audit synthesis

**Goal.** Validate / invalidate the Step 0 hypotheses against live DB
state + AMF parser dry-run. Adjust the P9.2 sequencing.

**Stack.** Docker up, ede-postgres healthy (`Up (healthy)`), alembic
HEAD = `0015` (post-P9.1c). 730 FR + 47 IT + 42 DE deals (DE matches
P9.1c reference).

Output artifacts:
- `data/audits/p92_consob_db_audit.csv` — full 47-deal dump.
- `data/audits/p92_amf_db_audit.csv` — full 730-deal dump.
- `data/audits/p92_amf_parser_dryrun.csv` — 10-deal parser-vs-truth.

## a) Consob root cause — Step 0 reading was inverted

**The 5/47 figure was the FAILURE count, not the success count.**

DB reality:
- **42 / 47** Consob deals have `offer_price` populated (89 %).
- **5 / 47** are NULL.
- **47 / 47** flagged `suspect_low_unverified` (the migration-0015
  default). Zero promotion to `verified_*` ever happened on Consob.

The 5 NULL deals:

| id | target_name | regulator_ref | deal_type | reason |
|---|---|---|---|---|
| 342 | Mediobanca-Banca di Credito Finanziario Spa | CONSOB-ops_montepaschi_20250714 | **opas** | OPS = share swap, no cash → legitimate NULL |
| 344 | Banca Popolare di Sondrio S | CONSOB-ops_Banca_Popolare_Sondrio_20250616 | **opas** | OPS share swap, legitimate NULL |
| 1035 | Monti Riffeser Srl | CONSOB-opa_morif_20250407 | opa_volontaire_totalitaria | needs investigation |
| 1039 | Piovan Spa | CONSOB-opa_Piovan_20250303 | opa_obligatoire | **font-encoding broken** — confirms Step 0 finding |
| 1040 | Comal Spa | CONSOB-opa_comal_20250217 | opa_volontaire_totalitaria | needs investigation |

So the **genuine** extraction-failure rate is 1-3 / 47 (Piovan plus
the two `opa_morif` / `opa_comal`), not 42 / 47. OPS share-swap deals
are legitimately NULL and should stay so until a separate
share-swap-specific extraction lands.

**Quick-win Consob — YES, identified, and it is NOT the cover-page
regex.** The blocker is **flag promotion**. All 47 deals carry the
default `suspect_low_unverified` flag, none have been promoted to
`verified_cash` despite 39-40 of them having clean, plausible
`offer_price` values. The promotion logic that BaFin received in
P9.1a was never ported to Consob.

There is also **one false-positive outlier** in the populated set:

| id | target_name | offer_price | issue |
|---|---|---|---|
| 1034 | Banco BPM Spa | 3 828 060 000 €/share | parser captured the **total controvalore** (deal size) instead of the unit price (`ops_Banco_BPM_20250428`, share-swap deal) |

This is one bug to fix during the Consob promotion logic — sanity
bounds on a per-share price (e.g., reject > 10 000 €).

### Adjusted Consob impact estimate

Step 0 estimated 5 → 30-35 / 47 from 3 fixes (label-anchor +
multi-page + OCR). **Wrong baseline.** Real numbers:
- Current: 42 extracted, 0 promoted, 5 NULL (2 legitimate OPS).
- After flag promotion (`P9.2-consob-promote`): ~38-40 / 47
  `verified_cash` (catches the genuine cash deals, skips the 2 OPS
  + Piovan + Banco-BPM outlier + the 2 `opa_morif`/`opa_comal`
  pending investigation).
- After OCR fallback + OPAS structured extraction (`P9.2-consob-b`):
  potentially recovers Piovan and the `morif`/`comal` if they're
  encoding issues, plus splits the OPAS Banca Sistema cash + share
  legs into `deal_consideration`. Marginal volume gain (1-3
  deals); main value is structural (3-regulator schema validation).

## b) AMF parser state — pipeline gap, not regex bug

**0 / 730 confirmed.** All deals at `parser_version=1`, all flagged
`suspect_low_unverified`.

The dry-run on the 10 Step-0-audited PDFs (`scripts/p92_amf_parser_dryrun.py`):

| ref | target | expected | parsed | status |
|---|---|---|---|---|
| 216C1735 | CEGID GROUP | 61.00 | 61.00 | **match** |
| 219C0051 | TESSI | 160.00 | 42.70 | mismatch (dividend trap) |
| 223C0044 | SERMA GROUP | (none) | (none) | match_none ✓ |
| 224C0830 | TIPIAK | 88.00 | (none) | **miss** |
| 224C0915 | TRAVEL TECH | 2.85 | 2.34 | mismatch (block-purchase trap) |
| 225C0021 | NEOEN | 39.85 | 39.85 | **match** |
| 225C0741 | FINANCIERE MONCEY | 133.00 | 5.83 | mismatch (anchor on footnote ratio?) |
| 225C0921 | M2I | 8.50 | 8.50 | **match** |
| 225C2081 | TAYNINH | 0.11 | 0.11 | **match** |
| 225C2156 | PRODWARE | 28.00 | (none) | **miss** |

Score: 5 match + 1 match_none + 2 miss + 2 mismatch = **6/10
correct, 4/10 wrong** on the audited sample.

This is **critically different** from a parser that never produces
output. The parser DOES extract on 7/10 PDFs (with 5/7 being
correct), but the DB still shows 0/730. The arithmetic is
incompatible with "parser broken everywhere" — it requires the
parser to NEVER RUN against the production corpus.

**Pipeline-gap evidence:**

```bash
# BaFin invokes parser:
src/ingestion/bafin/poller.py:135
  bafin_parser.extract_pdf_metadata(pdf_path) if pdf_path is not None ...

# Consob invokes parser:
src/ingestion/consob/poller.py:165
  consob_parser.extract_pdf_metadata(pdf_path) ...

# AMF: NO MATCH for extract_pdf_metadata outside parser.py itself.
$ grep -rn 'extract_pdf_metadata' src/ingestion/amf/
src/ingestion/amf/parser.py: (only the definition)
```

And `src/ingestion/amf/service.py:217-218` carries a deferred-TODO
comment:

> "longer used since BDIF doesn't expose price in the API; price is
> extracted from the PDF by the analyst/parser layer **later (phase
> 6)**".

Phase 6 was the scoring sprint — this never landed. The AMF parser
is fully implemented but **disconnected from the ingestion
pipeline**.

### Adjusted AMF impact estimate

- **Wire the existing parser into the AMF poller / backfill** (no
  regex change): if the dry-run 60-70 % match rate holds on the
  730-deal corpus, baseline goes from 0/730 to ~440-510/730 with
  `suspect_low_unverified` flag.
- Apply BaFin-style flag promotion: ~300-400/730 `verified_cash`
  (depending on outlier rejection bounds).
- THEN apply the regex hardening (Step 0's recommended verb
  discriminator + multi-tranche + trap rejection) on top — should
  take the verified count from ~350 to ~500-550/730. The 180-380
  long tail will be response-notes (legitimately no price) +
  share-swap OPEs + non-standard formats.

## c) ISIN claim — corrected

**Step 0 said:** "ISIN in filename, 100 % extractable".

**Reality:** the **PDF filename** is just the AMF reference code
(`226C0683.pdf` — short form). The longer code
`216C1735-FR0000124703-OP019-A06` that I quoted in Step 0 is the
**PDF body header** (line 4 of page 1), printed on every page.

So the claim "100 % extractable" still stands, but the
implementation must read page 1 line ~4 with a regex like
`^\s*(?P<ref>\d{3}C\d{4})-(?P<isin>[A-Z]{2}[A-Z0-9]{9}[0-9])-OP`,
not parse the filename. Tiny change to the spec — same effort
class, slightly different code path.

Spot check on 50 AMF `regulator_ref` rows: all match `^\d{3}C\d{4}$`
(7-char AMF ref). No ISIN baked into the DB column. Confirms
ISIN extraction is a brand-new addition, not a re-parse of existing
data.

## d) Adjusted recommendation

### Sequence (DÉCISION UTILISATEUR — 02d en premier comme layup low-risk)

User override on the original AMF-first ordering: **02d first**.
Rationale: the Consob promotion logic is a pure
SELECT-and-UPDATE script with bounded sanity checks, no parser
modification, no ingestion path change. It validates the
P9.1a-style promotion pattern on a second regulator (BaFin →
Consob) **before** the AMF wiring work introduces parser-output
volatility. Cost of getting 02d wrong: low (UPDATE rollback,
no schema change). Cost of getting 02a wrong: medium (parser
outputs propagate to ingestion + Phase-8 trading flow).

| # | Branch | Scope | Volume impact | Risk | Effort |
|---|---|---|---|---|---|
| 1 | `phase-09-02d-consob-promote-flags` | Mirror P9.1a flag promotion on Consob: sanity bounds (e.g. `0,01 € ≤ price ≤ 10 000 €/share`), promote `suspect_low_unverified` → `verified_cash` on plausible values; reject Banco BPM outlier (3.8B€/share) explicitly via bounds | 0 verified → ~38 `verified_cash`/47 | **LOW** (layup) | 1 day |
| 2 | `phase-09-02a-amf-wire-parser` | Wire `extract_pdf_metadata` into AMF service; backfill script for 730 historical deals; **includes the `\xa0` regex fix at parser.py:66 + :278 as a free atomic commit inside this branch** | 0/730 → ~450/730 extracted, ~300/730 `verified_cash` after promotion bounds | MEDIUM | 1-2 days |
| 3 | `phase-09-02b-amf-regex-hardening` | Verb discriminator (`s'engage` vs `a acquis`), trap rejection (dividend, fees, convertibles), multi-tranche `par action` qualifier | +100-150 deals to `verified_cash` (350 → ~500) | MEDIUM | 3-4 days |
| 4 | `phase-09-02c-amf-isin-header` | Page-1 header regex `^\d{3}C\d{4}-(<ISIN>)-OP` | 730/730 ISIN populated | LOW | 0.5 day (parallel-friendly) |
| 5 | `phase-09-02e-consob-opas-mixed` | Banca Sistema-class structured cash+share extraction; reuse P9.1c `deal_consideration` | +1-2 mixed deals correctly split | LOW | 1-2 days |
| 6? | `phase-09-02f-ocr-fallback` | **CONDITIONAL** — Tesseract OCR fallback when PyMuPDF text density < threshold. Only triggered if post-02a/02b/02d the long tail of `pdf_text_extraction_failed` deals (Piovan / morif / comal class) exceeds 5% of the FR+IT corpus | recover 1-3 IT + tail of FR | conditional | TBD |

Sequencing rationale (02d → 02a → 02b → 02c → 02e[+02f?]):
- **02d ships ~38 `verified_cash` Consob candidates in 1 day**,
  proving the promotion pattern on a second regulator before any
  AMF wiring touches production code. Phase-8 trading flow gets a
  measurable volume bump immediately.
- **02a follows** with the higher-impact-but-higher-risk AMF
  wiring; the promotion pattern is now battle-tested.
- **02b** layers regex hardening on top — safe because 02a has
  already validated the wiring and the dry-run baseline.
- **02c** (ISIN header) is small and ships anywhere; treated as a
  4th-position default but could be parallelised by a second
  author or interleaved.
- **02e** (Consob OPAS) is structural validation of the P9.1c
  `deal_consideration` schema on a 3rd regulator; small volume but
  small effort.
- **02f** is gated on observed long-tail size after 02a/b/d
  ship. If the residual `pdf_text_extraction_failed` flag count
  stays under 5% of the joint corpus, OCR is **deferred to P10**
  with a `pdf_text_extraction_failed` flag + manual_review marker
  rather than adding a Tesseract system dep now.

### Long tail OCR — conditional 02f

Decision: **do not implement OCR now.** The Piovan-class extraction
failures (1 confirmed in 10 sampled IT PDFs, 0 in the AMF sample)
will be flagged with a new `pdf_text_extraction_failed` quality
flag (added in 02a as part of the AMF parser wiring — gated by a
"text length < N chars on first 5 pages" heuristic). If the
post-02a/02b/02d residual count stays under 5% of the joint
777-deal corpus (~38 deals), OCR is logged as P10 debt rather
than implemented in P9.2. If it exceeds 5%, 02f is greenlit.

### Bugs collatéraux 02a — confirmed atomic fix

The `\xa0` literal bugs at `src/ingestion/amf/parser.py:66`
(`_PRICE_REGEX` character class contains `\\xa0` = 4 literal
chars, not the NBSP byte) and `:278` (`raw.replace("\\xa0", "")`
also a 4-char no-op) will land as the **first atomic commit** of
the `phase-09-02a-amf-wire-parser` branch, ahead of the wiring
work. This isolates the encoding fix from the wiring change so
a regression in either is locatable via `git bisect`.

### Open bugs noticed during the dry-run

1. **`parser.py:66` literal `\\xa0`** — the raw-string concatenation
   makes the regex match the 4 characters `\`, `x`, `a`, `0`, not
   the non-breaking-space character `\xa0`. Fix: drop the
   double-backslash, use `\xa0` directly inside the character
   class.
2. **`parser.py:278` literal `\\xa0`** in `raw.replace("\\xa0", "")`
   — same bug, replaces nothing useful. Fix:
   `raw.replace("\xa0", "")`.
3. **MONCEY parsed 5.83** — could not reproduce in Step 0 text
   dump (line 50 shows `5,67 actions UMG` — share ratio). The
   `5,83` must come from a region I didn't read; needs a 5-line
   `print(text[m.start()-50:m.end()+50])` in the dry-run script
   to nail the source. Probably a page-3+ amount near a `€`.

These two encoding bugs may also explain part of the dry-run
mismatches and should land in 02a (parser wiring) since they're
trivial.

## e) Consob quick-win inclusion in current PR?

The user gate was: "Si Consob quick-win plumbing identifié → faire
en premier (1-2h)". The quick-win IS identified — **flag promotion**.

**Recommendation: separate PR.**
- The current branch `phase-09-02-amf-consob-audit` is docs-only +
  one diagnostic script (`scripts/p92_dump_pdf_text.py`,
  `scripts/p92_amf_parser_dryrun.py`). Clean commit history, no
  DB write, no migration. Ships immediately as Step 0 deliverable.
- The Consob promotion logic touches DB + carries sanity bounds +
  needs unit tests. It is its own concern. Putting it in the
  docs PR would muddle the review focus and require a code-review
  pass on a doc PR.
- Sequencing: ship Step 0 PR now (docs gate for P9.2 impl),
  branch `phase-09-02d-consob-promote-flags` immediately after
  merge with its own PR. Estimated overlap: hours, not days.

The dry-run script `scripts/p92_amf_parser_dryrun.py` is a
diagnostic / one-shot; it does not exercise any production code
path beyond calling the existing `extract_pdf_metadata`. Safe to
include in the docs PR.

## Decisions log (validated by user post-checkpoint)

1. **PR Step 0 docs-only** — Consob promotion logic goes on its
   own branch `02d` after Step 0 ships.
2. **Sequencing revised to 02d → 02a → 02b → 02c → 02e** — 02d
   first as a low-risk layup that validates the promotion pattern
   before AMF wiring; full rationale in the table above.
3. **Banco BPM outlier** — handled in 02d via per-share bounds
   check (`price ≤ 10 000 €/share`). Deeper investigation of the
   `controvalore`-vs-`unit_price` parser confusion is logged as
   P10 debt unless it recurs in another deal.
4. **OCR (02f)** — gated on observed long-tail size after 02a /
   02b / 02d ship. Default: do not implement; mark failed
   extractions with `pdf_text_extraction_failed` (introduced in
   02a) and defer Tesseract to P10 if the long tail stays <5%.

Ready for commit + PR.
