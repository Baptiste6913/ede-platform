# P9.2 Step 0 — comparative synthesis (AMF vs Consob)

**Inputs.** `p92_amf_extraction_manual.md` (10 PDFs, 2016-2025) +
`p92_consob_extraction_manual.md` (10 PDFs, 2024-2026). Sample size
20 PDFs total, year-folder-stratified, no DB-driven completion-label
split (Postgres offline).

**Purpose.** Empirically inform the P9.2 implementation brief
(extension of P9.1a structured-extraction to AMF + Consob), with
effort estimates per jurisdiction and a recommended sequencing.

---

## a) Confirmed anchor patterns

### AMF — French language, narrative document

The AMF "Décisions et Informations" PDFs (1-5 pages of dense
procedural prose) carry the offer price inside running narrative
text. No structured cover page; the anchor is an idiomatic
French formula.

| # | Anchor | Sample frequency | Example |
|---|---|---|---|
| 1 | `s'engage irrévocablement à acquérir … au prix unitaire de <X> €` | 5 / 9 priced AMF PDFs | NEOEN, TIPIAK, M2I, Travel Tech, TAYNINH |
| 2 | `au prix de <X> € par action` | 5 / 9 priced (overlaps with #1) | CEGID, TIPIAK retrait leg, NEOEN action variant |
| 3 | `indemnisation [unitaire] [de] <X> € [par action]` (retrait obligatoire) | 4 / 9 priced | Travel Tech, M2I, PRODWARE, MONCEY |
| 4 | `<X> € par action <Target> apportée` (mixed-offer cash branch) | 1 / 9 priced | MONCEY |
| 5 | `au prix unitaire de <X> euros` (no `€`, plural) | 1 / 9 priced | TESSI 2019 |

**Compact regex shape** (informative — actual parser will refine):

```text
(s'engage[^.]{0,80}à\s+acquérir|indemnisation)
  [^.]{0,60}
  (?:au\s+)? prix \s+ (?:unitaire\s+)? (?:relevé\s+)? de
  \s+ <amount>
  \s* (?:€|euros?)
  (?:\s+ par \s+ action (?:\s+ <TARGET> \s+ apportée)?)?
```

### Consob — Italian language, structured cover page

The Consob "Documento di Offerta" PDFs (100-200+ pages) place the
offer price on a **standardized cover page** with a labeled field.
The anchor is a header-style label, not narrative.

| # | Anchor | Sample frequency | Example |
|---|---|---|---|
| 1 | `CORRISPETTIVO UNITARIO OFFERTO\n+ Euro <X> per ciascuna azione` | 8 / 9 readable | Civitanavi, anima, bialetti, almawave, Eles, Ferretti, Banca Sistema |
| 2 | Label variant `CORRISPETTIVO UNITARIO OFFERTO PER AZIONE ORDINARIA` | 1 / 9 | almawave |
| 3 | Connector variant `per ogni azione` | 1 / 9 | CIR |
| 4 | Title-case label `Corrispettivo unitario offerto` | 1 / 9 | Medica |
| 5 | Mixed-offer composite (OPAS): `Un corrispettivo complessivamente pari a Euro <Total>` followed by `(a) Euro <Cash> in contanti` and `(b) … n. <N> azioni <Acquirer> per ciascuna Azione <Target>` | 1 / 9 | Banca Sistema |

**Compact regex shape** (informative):

```text
(?im)
  CORRISPETTIVO \s+ UNITARIO \s+ OFFERTO (?:\s+ PER \s+ AZIONE \s+ ORDINARIA)?
  \s*\n+
  (?:Euro|EUR|€) \s* <amount>
  \s* (?:\(.+?\))?           # optional "(spelt out)" or "(cum div)" notes
  \s* (?:cum \s+ dividend(?:o)?)?
  \s+ per \s+ (?:ciascuna|ogni) \s+ azione
```

**Key structural finding:** AMF requires *narrative* parsing
(verb-based discrimination of offer vs block-purchase); Consob
requires *structured-field* parsing (label-anchored on a known cover
template).

---

## b) Confirmed traps

### AMF traps — diverse, narrative

| Trap class | Pattern | Sample occurrences | Discriminator |
|---|---|---|---|
| Block purchase price | `a acquis … au prix unitaire de <X> €` | 6 / 10 | verb `a acquis` vs `s'engage à acquérir` |
| Complément de prix | `complément de prix de <X> €` | 1 / 10 | noun `complément` |
| Dividend / distribution | `dividende … <X> € par action`, `Distribution … <X> euro par action` | 2 / 10 | nouns `dividende`, `Distribution`, `acompte` |
| Transaction fees | `… dans la limite de <X> € par dossier` | 2 / 10 | clause `par dossier` |
| Convertible / warrant prices | `<X> € par (BAAR\|BSA\|océane)` | 3 / 10 | `par <non-action>` clause |
| Acquirer ISIN | second ISIN belonging to the buyer | 1 / 10 (MONCEY) | filename-anchored target ISIN takes priority |
| French number formatting | `101 382,00 €` (space thousand separator) | 1 / 10 (NEOEN) | regex must accept `\s` thousand separator |

### Consob traps — few in cover, mostly structural

| Trap class | Pattern | Sample occurrences | Discriminator |
|---|---|---|---|
| Number in words | `Euro 6,17 (sei virgola diciassette)` | 2 / 10 | strip parentheticals, keep numeric |
| `cum dividendo` qualifier | `Euro 7,00 cum dividendo, ossia inclusivo …` | 3 / 10 | qualifier does *not* change price |
| HK dual-listing identifier | `09638.HK` | 1 / 10 (Ferretti) | exclude `XXXXX.HK` from ISIN regex |
| Mixed-offer share ratio | `n. 21 azioni Kruso Kapital` | 1 / 10 (Banca Sistema) | "21" is a count not a price; anchor on `Euro` token |
| Mixed-offer cash leg | `(a) Euro 1,382 in contanti` | 1 / 10 (Banca Sistema) | pick *total* `Euro 1,80`, store leg components in `deal_consideration` |
| Esborso Massimo (page 3+) | total disbursement on financing section | All long docs | restrict scan to first 5 pages OR anchor on `CORRISPETTIVO UNITARIO` |
| Image/font-broken cover | extracted text = scrambled symbols | 1 / 10 (Piovan) | OCR fallback required |
| Page-1 legal disclaimer | HK Takeovers Code warning pushes cover to page 2 | 1 / 10 (Ferretti) | scan pages 1-5, not just page 1 |

---

## c) ISIN coverage estimate

| Jurisdiction | ISIN position | Empirical sample coverage | Extraction cost |
|---|---|---|---|
| **AMF** | Filename prefix (`<amf_ref>-<ISIN>-OP…`) + document header on every page | **10 / 10 (100 %)** | Trivial — filename regex `^\d{3}C\d{4}-([A-Z]{2}[A-Z0-9]{9}[0-9])-` |
| **Consob** | NOT on cover page, NOT in filename. Present in body (Section B.2 "Soggetto Emittente") on deeper pages | **0 / 10 from first 5 pages** (sample limited to first 5 pages) | Medium — must scan deeper pages, locate ISIN regex with `[A-Z]{2}[A-Z0-9]{9}[0-9]` + Luhn validation |

**Implication:** AMF ISIN extraction is essentially free in P9.2.
Consob ISIN extraction needs a separate pass over deeper sections of
the offer document. The Consob deliverable should NOT block on ISIN
in the first impl pass — `offer_price` can land first, ISIN can land
in P9.2b as a follow-up.

---

## d) Offer-type mix (sample only, n = 10 each — not representative of full corpus)

| Type | AMF (n=10) | Consob (n=10) | BaFin reference (P9.1c) |
|---|---|---|---|
| Cash pure | 8 (incl. 1 multi-tranche NEOEN) | 5 + 1 obbligatoria + 2 parziale = 8 | 25-30 / 42 labelled |
| Mixed (cash + share alternative or composite) | 1 (MONCEY) | 1 (Banca Sistema OPAS) | 2 (Commerzbank, ProSieben) |
| Share swap pure | 0 | 0 | 0 |
| Self-tender / buyback | 0 | 1 (CIR) | — |
| N/A — response/supplementary PDF | 1 (SERMA) | 1 (Piovan extraction failure) | 0 |

**Caveat.** The samples (10 each) are not stratified by completion
label and not representative of the 730 FR / 47 IT corpora. They
*are* sufficient to confirm that:
- Both jurisdictions are dominated by cash deals.
- Mixed offers exist in both with structurally equivalent two-leg
  patterns reusable from P9.1c BaFin work.
- Share swap pure (OPE in FR, OPS Volontaria di Scambio in IT) was
  not observed in this sample and should be planned for as a
  long-tail case.

---

## e) Effort estimate — AMF parser hardening

**Verdict: MEDIUM-HARD.**

Reasons it is harder than BaFin (P9.1a):
- **Multi-PDF per deal lifecycle.** AMF publishes 3-5 PDFs per
  offer (deposit notice, response note, conformity decision,
  closing notices). The parser needs to know which doc types
  carry the price and skip the others (otherwise the parser
  triggers a "no price found" flag on legitimate-empty docs).
- **Block-purchase trap is structurally identical to the offer
  anchor.** Both use `au prix unitaire de X € par action`; the
  discriminator is the **verb** (`a acquis` vs `s'engage à
  acquérir`). Pure regex is insufficient — needs verb-anchored
  context windows or a small state machine.
- **French number formatting.** `101 382,00 €` with space (or
  non-breaking space) as thousand separator. Inherited Italian
  regex likely fails on this.
- **Multi-tranche offers** (NEOEN: shares + 2 OCEANE convertible
  series, each priced separately). Parser must qualify the
  matched amount with `par action` and reject `par océane`, `par
  BAAR`, `par BSA`, `par bon`.
- **Currency variants.** `€`, `euros`, `euro` (singular) — all
  observed.

Reasons it is *easier* than BaFin in places:
- **ISIN is free** — filename-encoded (`<ref>-<ISIN>-OP…`).
- **Short PDFs** (1-5 pages) — entire content can be scanned.
- **Decimal precision is mild** (2 decimals dominant, with
  3-decimal exceptions).

**Estimated impact of impl on 730 FR corpus:**
- A complete parser (anchor + verb discriminator + multi-tranche +
  trap rejection) targeting *deposit notice + conformity decision*
  doc types should plausibly capture 60-75 % of the 730 deals
  (most of which are simple cash OPA/OPAS). The remaining 25-40 %
  will be a mix of: response notes (no price by design),
  archival / metadata-only docs, share-swap-pure OPEs, and
  edge-case formatting.

---

## f) Effort estimate — Consob parser hardening

**Verdict: MEDIUM.**

Reasons it is easier than BaFin:
- **Standardized cover page** with explicit `CORRISPETTIVO
  UNITARIO OFFERTO` label. A label-anchored regex needs no verb
  discrimination, no narrative state machine.
- **Few traps in the cover region.** Block purchase prices, fees,
  and dividends live deeper in the doc — restricting the scan to
  pages 1-5 sidesteps almost all of them.
- **Existing partial-success baseline (5 / 47).** The current
  parser already extracts the *first* EUR amount it finds — most
  failures are below the cover-page level (font encoding, page-2
  placement, label variants), not regex incorrectness.

Reasons it is non-trivial:
- **OCR fallback required.** 1 / 10 cover pages was unparseable
  by PyMuPDF (Piovan: scrambled font encoding). Extrapolated to
  the 47-deal corpus that's 5-10 OCR-only PDFs. Need to add
  `pytesseract` to the dependency tree, or use PyMuPDF's
  `get_textpage_ocr()` if Tesseract is available system-side.
- **Multi-page cover.** Ferretti's HK dual-listing forces the
  cover to page 2. Parser must scan pages 1-5, ideally with a
  shortcut on the page that contains the label.
- **OPAS mixed offers.** Banca Sistema's composite consideration
  (cash + share at ratio 21:1) reuses the BaFin P9.1c
  `deal_consideration` two-leg structure, but the Italian
  language anchors differ (`in contanti` for cash leg; `n. X
  azioni <Acquirer> per ciascuna Azione <Target>` for share leg).
- **ISIN extraction non-trivial.** Not on cover; requires
  deeper-page scan (Section B.2).

**Estimated impact on 47 IT corpus** (sequential gains, with
diminishing returns):
- **Label-anchor regex** (case-insensitive, scan pages 1-5):
  baseline 5 / 47 → ~25 / 47 (recover non-page-1 covers and
  label variants).
- **+ OCR fallback** when text density < threshold:
  ~25 / 47 → ~32-35 / 47 (recover Piovan-class scanned PDFs).
- **+ OPAS mixed-offer two-leg extraction:** structurally
  important (analog of P9.1c) but small absolute impact (1-3
  deals).
- Residual 10-15 will be edge-cases: malformed PDFs, partial
  offers with non-standard cover, withdrawn offers, etc. — same
  long tail as BaFin's `manual_review` flag.

---

## g) Recommended sequencing — AMF or Consob first?

**Recommendation: Consob first, AMF second. Sequential, not parallel.**

Reasons:

1. **Higher hit-rate per impl effort on Consob.** The Consob
   parser already has a foundation (5 / 47 hit), the failure
   modes are structural (page placement, OCR, label variants) not
   linguistic, and the 3 quick fixes (label anchor + multi-page +
   OCR) plausibly take 5 → 30 deals. That's 25 deals enabled per
   ~1 week of work.

2. **AMF needs the verb-discrimination work that doesn't apply
   to Consob.** Building verb-based context windows is a piece of
   parser machinery that is general — but writing it as part of
   AMF P9.2 means the Consob lift can ship first and provide
   immediate signal to the Phase-8 trading flow.

3. **The OPAS Banca Sistema work re-validates the P9.1c
   `deal_consideration` schema** on a third regulator, giving a
   3-jurisdiction smoke test for that schema before AMF MONCEY-
   style mixed-offer work piles on. Lower risk of late-discovered
   schema gaps.

4. **AMF's filename-ISIN free win** can be released independently
   as a tiny side-PR before the AMF parser hardening starts —
   trivially populates ISINs on the 730 FR corpus without
   touching the price extraction logic.

**Branch naming suggestion:**
- `phase-09-02a-consob-cover-anchor` (label + multi-page + OCR;
  no OPAS yet)
- `phase-09-02b-consob-opas-mixed` (Banca Sistema-class mixed)
- `phase-09-02c-amf-filename-isin` (trivial — drop ASAP)
- `phase-09-02d-amf-narrative-extraction` (verb discriminator +
  trap rejection + multi-tranche)

Each branch is independently mergeable. **Parallelism is
possible** if a second author is available — the four branches
don't share files (Consob: `src/ingestion/consob/parser.py`; AMF:
`src/ingestion/amf/parser.py`). With a single author,
recommended order is **02a → 02b → 02c → 02d**.

---

## h) Quick-win question on the 5 / 47 working Consob deals

Without DB access we cannot identify *which* 5 deals have populated
`offer_price`. From the parser code at
`src/ingestion/consob/parser.py` l. 47-50 (single first-amount EUR
regex), the working set is almost certainly the deals whose **cover
page parses cleanly with PyMuPDF**, **places the cover on page 1**,
and where the **first EUR amount in the parsed text happens to be
the offer price**.

In the 10-PDF sample, **7 / 10 fit that profile** (Civitanavi, CIR,
anima, bialetti, almawave, Eles + Banca Sistema partial). If the
sample is representative, ~70 % of 47 = ~33 deals should currently
work — but only 5 do. That gap suggests **at least one of the
following is also breaking**:

- The parser may not run on every PDF (e.g., a poller skip
  condition).
- The parser may run, extract a price, but be flagged as
  `suspect_low` by the P9.1a quality flag (e.g., price < 1 € is
  flagged) and not get promoted.
- The Consob ingestion may have a different code path than BaFin
  that wasn't included in the P9.1a flag promotion logic.

This is an **investigation item for the P9.2 impl brief**, not
something Step 0 can resolve from PDFs alone. The first action of
the impl phase should be a 1-hour DB sanity audit:
- Query `Deal WHERE juridiction = 'IT' AND offer_price IS NOT NULL`
  → which 5? Map them to PDF filenames.
- Query `Deal WHERE juridiction = 'IT' AND offer_price IS NULL`
  with `offer_price_quality_flag` distribution → what flags are
  blocking promotion?

The Step 0 audit established that the *language patterns* are
not the bottleneck — the bottleneck is parser plumbing and OCR.

---

## Cross-jurisdiction summary table

| Dimension | AMF | Consob | BaFin (reference P9.1a) |
|---|---|---|---|
| Doc length per PDF | 1-5 pages | 100-200+ pages | 100+ pages |
| Doc type homogeneity | Multiple types per deal (3-5) | One main `Documento di Offerta` per deal | One main `Angebotsunterlage` |
| Anchor style | Idiomatic narrative | Labeled cover field | Labeled section (`Geldleistung`) |
| Anchor regex difficulty | Hard (verb discrim.) | Easy (label-anchor) | Medium (label + line-anchor) |
| ISIN position | Filename + every page | Body (page 30+) | Body, requires structured pass |
| Number formatting | Space thousand sep | Standard `,XX` | Standard `,XX` |
| Currency variants | `€`/`euros`/`euro` | `Euro`/`euro`/`EUR`/`€` | `Euro`/`EUR`/`€` |
| Mixed-offer pattern | Alternative branches | Composite consideration (OPAS) | Geldleistung + Gewährung |
| Mixed-offer prevalence (sample) | 1 / 10 | 1 / 10 | 2 / 42 labelled |
| OCR required | Not observed | Yes (Piovan-class) | Not observed |
| Effort vs BaFin | ↑ harder (verb logic + traps) | ≈ similar (OCR + variants) | Baseline |
| Estimated hit-rate on corpus, end-state | ~60-75 % | ~70-80 % | ~95 % (post P9.1a) |

## Open questions for the P9.2 impl brief

1. **Which 5 / 47 Consob deals are currently populated?** Need DB
   query. This validates or invalidates the "70 % should work" sample
   extrapolation.
2. **Is the AMF parser currently running on every PDF, or only on
   specific doc types?** The 0 / 730 hit rate suggests a code path
   problem distinct from the regex — confirm via a parser dry-run
   on 10 of the audited PDFs.
3. **What's the dependency on OCR?** Acceptable to add `pytesseract`
   + Tesseract system dep, or should we stay text-only and accept
   the Piovan-class long tail?
4. **Sequencing inside P9.2:** confirm the 02a/02b/02c/02d
   recommendation, or override.

These are open inputs to the P9.2 implementation brief, not Step 0
deliverables.

---

## STOP — checkpoint [Step0-C]

This document is the Step 0 synthesis. No code touched. No commit
issued yet (per brief). Awaiting user validation before:
- Atomic commit of the Step 0 artifacts (CSVs + 3 docs).
- Drafting the P9.2 implementation brief.
- Branching `phase-09-02a-consob-cover-anchor`.
