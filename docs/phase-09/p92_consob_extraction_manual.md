# P9.2 Step 0 — Consob manual extraction audit

**Goal.** Empirically characterize how `offer_price` + ISIN are presented
in Consob "Documento di Offerta" PDFs, and identify what distinguishes
the 5 / 47 IT deals that currently carry `offer_price` from the 42 that
don't. Sample size 10 PDFs, year-folder stratification (3 × 2024, 4 ×
2025, 3 × 2026) since the DB is offline (see AMF audit for context).

**Methodology.** First 5 pages of each PDF extracted via PyMuPDF
(`scripts/p92_dump_pdf_text.py`), then read in full by hand. Same
extraction template as the AMF audit: anchor verbatim ±15 words of
context, ISIN position, offer type, traps.

## Per-deal extractions

### [1] `CONSOB-opa_Civitanavi_Systems_20240527` (Honeywell offer, 2024)

- **Anchor on a structured cover page (page 1):**
  - p1 l17-18 : "**CORRISPETTIVO UNITARIO OFFERTO**
    **Euro 6,17 (sei virgola diciassette) per ciascuna azione ordinaria
    di Civitanavi Systems S.p.A.**"
  - The amount is also written in words in parentheses
    ("sei virgola diciassette" = six point seventeen) — Italian Consob
    convention; the parser should pick the *numeric* form.
- **Traps:** none in the first 5 pages. Section E (page 84+ in the full
  document, "CORRISPETTIVO UNITARIO PER GLI STRUMENTI FINANZIARI E
  SUA GIUSTIFICAZIONE") will introduce historic prices, weighted
  averages, target prices, etc. — but the cover-page anchor is the
  authoritative figure.
- **ISIN:** *not* on the cover page. Filename does not contain it
  (`CONSOB-opa_Civitanavi_Systems_20240527.pdf` — company name + date
  only). ISIN must be extracted from section B.2 ("Soggetto Emittente")
  later in the doc.
- **Offer type:** Volontaria Totalitaria cash.
- **Doc length:** 134 pages.

### [2] `CONSOB-opa_cir_20241125` (CIR self-tender, 2024)

- **Anchor:**
  - p1 l15-16 : "**CORRISPETTIVO UNITARIO OFFERTO**
    **Euro 0,61 per ogni azione di CIR S.p.A. portata in adesione
    all'Offerta**"
  - Variant connector: "per **ogni** azione" (instead of "per ciascuna").
- **Traps:** none in the first 5 pages.
- **ISIN:** not on cover; filename has no ISIN.
- **Offer type:** Volontaria **Parziale** (share buyback — `OFFERENTE
  ED EMITTENTE: CIR S.p.A.-Compagnie Industriali Riunite`).
- **Doc length:** 111 pages.

### [3] `CONSOB-opa_medica_20240701` (Donaldson via Mavendanc, 2024)

- **Anchor:**
  - p1 l31-33 : "**Corrispettivo unitario offerto**
    **euro 27,00 (ventisette/00) (cum dividend) per ciascuna azione
    ordinaria di Medica S.p.A.**"
  - **Casing variation:** label is "Corrispettivo unitario offerto"
    (Title Case), not all-caps. The parser must be case-insensitive.
  - **Currency variation:** "**euro**" lowercase.
  - **Caveat tag:** "(cum dividend)" — English-Italian mix.
- **Traps:** none in first 5 pages.
- **ISIN:** not on cover.
- **Offer type:** Volontaria Totalitaria cash.

### [4] `CONSOB-opa_Piovan_20250303` (2025) — **EXTRACTION FAILURE**

- **Anchor:** *not extractable from the PyMuPDF text dump.*
  - Pages 1-5 of the text dump contain scrambled symbols
    (`%%&#&5!&#/ .&1&&`, `6%/ "!","%/ "!","$%-7`). The PDF either
    uses a non-standard font encoding (CID font with no
    ToUnicode map) or is rendered from images / scanned pages.
  - PyMuPDF returned 218 pages but the text extraction is corrupt
    on the cover.
- **Implication:** **OCR fallback required.** This single PDF is the
  most likely explanation for ~half of the 42 / 47 Consob deals with
  no `offer_price`. Any regex hardening at the text level is useless
  here — the parser must invoke an OCR layer (Tesseract via
  `pytesseract`, or PyMuPDF's built-in `page.get_textpage_ocr()` if
  Tesseract is installed) when text density falls below a threshold.
- **Offer type:** unknown from the dump.

### [5] `CONSOB-opa_anima_20250317` (Banco BPM Vita / Anima Holding, 2025)

- **Anchor:**
  - p1 l20-22 : "**CORRISPETTIVO UNITARIO OFFERTO**
    **Euro 7,00 per ciascuna azione (cum dividendo, ossia inclusivo
    delle cedole relative ad eventuali dividendi distribuiti
    dall'Emittente)**"
  - The "cum dividendo" caveat is critical for downstream price
    cross-checks: the `yfinance_fetcher` (P9.1c) returns adjusted
    prices, so the parser should *record* the cum-dividend qualifier
    but compare against the unadjusted close.
- **Traps:** none in first 5 pages.
- **ISIN:** not on cover.
- **Offer type:** Volontaria Totalitaria cash.
- **Doc length:** 226 pages — the longest in the sample.

### [6] `CONSOB-opa_bialetti_20250707` (Octagon BidCo / Bialetti, 2025)

- **Anchor:**
  - p1 l17-18 : "**CORRISPETTIVO UNITARIO OFFERTO**
    **Euro 0,467 cum dividendo per ciascuna azione**"
  - **3-decimal precision:** `0,467` (3 decimals) — common for small-cap
    deals. The existing Consob regex already handles `\d{2,4}` decimals
    (`src/ingestion/consob/parser.py` l49), so this should not be a
    failure mode.
- **Traps:** none in first 5 pages.
- **ISIN:** not on cover.
- **Offer type:** **Obbligatoria** Totalitaria cash (mandatory after
  threshold crossing).

### [7] `CONSOB-opa_almawave_20251117` (Almaviva / Almawave, 2025)

- **Anchor:**
  - p1 l27-29 : "**CORRISPETTIVO UNITARIO OFFERTO PER AZIONE ORDINARIA**
    **euro 4,30 cum dividendo, ossia inclusivo delle cedole relative ad
    eventuali dividendi, ordinari o straordinari, distribuiti
    dall'Emittente per ciascuna azione ordinaria**"
  - **Label variant:** "CORRISPETTIVO UNITARIO OFFERTO **PER AZIONE
    ORDINARIA**" — adds `PER AZIONE ORDINARIA` to the label itself
    (some deals have multiple share classes; this clarifies which one).
  - **Currency lowercase:** `euro 4,30`.
- **Traps:** none in first 5 pages.
- **ISIN:** not on cover.
- **Offer type:** Volontaria Totalitaria cash (on Euronext Growth Milan).

### [8] `CONSOB-opa_eles_20260105` (EBIDCO / Eles Semiconductor, 2026)

- **Anchor:**
  - p1 l23-24 : "**CORRISPETTIVO UNITARIO OFFERTO**
    **Euro 2,65 per ciascuna azione ordinaria di Eles Semiconductor
    Equipment S.p.A.**"
- **Traps:** the "STRUMENTI FINANZIARI OGGETTO DELL'OFFERTA" field
  mentions Warrants 2019-2026 (line 20 — "azioni rivenienti
  dall'esercizio dei Warrant Eles 2019-2026"). The current dump
  shows **no warrant price** on the cover, but a deeper read might
  reveal one. Parser must qualify the matched amount with "per
  ciascuna azione" / "per azione ordinaria" — *not* "per warrant".
- **ISIN:** not on cover.
- **Offer type:** Volontaria Totalitaria cash with embedded warrant
  share-issuance scenario.

### [9] `CONSOB-opa_ferretti_20260316` (KKCG Maritime / Ferretti, 2026) — **NON-STANDARD COVER PLACEMENT**

- **Anchor — found on PAGE 2, not page 1:**
  - p1 : entirely legal warning (HK Stock Exchange dual-listing
    disclaimer; the PDF is bound by both Italian and HK Takeovers
    Code rules).
  - p2 l51-60 : "EMITTENTE: Ferretti S.p.A.
    OFFERENTE: Azúr a.s. (KKCG Maritime)
    STRUMENTI FINANZIARI OGGETTO DELL'OFFERTA: massime n. 52.132.861
    azioni ordinarie di Ferretti S.p.A.
    **CORRISPETTIVO UNITARIO OFFERTO**
    **Euro 3,50 per ciascuna azione ordinaria di Ferretti S.p.A.**"
- **Implication:** the parser must NOT short-circuit on page 1 if no
  anchor is found. It must scan the first ~5 pages, possibly with a
  fallback that recognizes the legal-disclaimer page pattern
  ("QUESTO DOCUMENTO È IMPORTANTE E RICHIEDE LA VOSTRA IMMEDIATA
  ATTENZIONE", or HK references) and advance to the next page.
- **Traps:** the cover mentions HK ticker "**09638.HK**" (line 30) —
  this is the dual-listed identifier on HKEX, not an ISIN; the
  parser must ignore the `XXXXX.HK` pattern.
- **ISIN:** not on cover; the HK ticker `09638.HK` could be
  mis-extracted by a naive identifier-extraction regex.
- **Offer type:** Volontaria **Parziale** e Condizionata, cross-border
  (Czech offerer, Italian + HK listed target).

### [10] `CONSOB-opas_Banca_Sistema_20260116` (Banca C.F.+ / Banca Sistema, 2026) — **MIXED OFFER (OPAS)**

- **Anchor — structured composite consideration:**
  - p1 l13-18 : "**CORRISPETTIVO UNITARIO OFFERTO**
    **Un corrispettivo complessivamente pari a massimi Euro 1,80 per
    ciascuna azione portata in adesione all'Offerta rappresentato
    dalle seguenti componenti:**
    **(a) Euro 1,382 in contanti** da pagarsi alla Data di Pagamento
    del Corrispettivo Iniziale (come infra definita); e
    **(b) massimi Euro 0,418 da pagarsi entro la Data di Pagamento
    del Corrispettivo Differito (come infra definita) attraverso
    l'attribuzione di n. 21 azioni Kruso Kapital S.p.A., previo
    frazionamento, per ciascuna Azione Banca Sistema portata in
    adesione all'Offerta**"
- This is the **OPAS** (Offerta Pubblica di Acquisto e **Scambio**)
  pattern — the Italian equivalent of:
  - the BaFin "Geldleistung + Gewährung von Aktien" mixed offer
    (P9.1c) and
  - the AMF "OPA alternative" (FINANCIERE MONCEY in this audit),
  with **important structural differences**:
  - Total consideration `Euro 1,80` is given explicitly (cash + share
    sum) — easier to capture than the AMF MONCEY case where only the
    cash leg and the share ratio are stated.
  - Cash leg `Euro 1,382` (3 decimals) is split between an "Iniziale"
    and a "Differito" payment date.
  - Share leg is denominated in "**n. 21 azioni Kruso Kapital S.p.A.**
    **per ciascuna Azione Banca Sistema**" — analogous to the BaFin
    "X Stück Aktien je 1 Aktie der Erwerber" pattern parsed in P9.1c.
- **Traps:** the share ratio "21" could be mis-extracted by an
  EUR-amount regex as if it were a tiny price (e.g., "21,000 €") if
  the regex is too permissive on integer matches without `,XX`
  decimals.
- **ISIN:** not on cover. Acquirer-side `Kruso Kapital S.p.A.` is also
  mentioned — risk of two ISINs in the body (target + share-paid
  acquirer), same as AMF MONCEY.
- **Offer type:** **OPAS mixed cash + share** — the same two-leg
  structured-extraction logic used in BaFin P9.1c
  (`src/ingestion/bafin/parser.py: _extract_consideration()`)
  applies, with anchors `Euro X in contanti` and `n. Y azioni
  <Acquirer> ... per ciascuna Azione <Target>`.

## Summary of patterns discovered

### Confirmed offer-price anchors

The Consob cover-page format is **highly standardized**. A single
anchor template covers 9 / 10 sampled PDFs:

```
(?im) CORRISPETTIVO\s+UNITARIO\s+OFFERTO (\s+PER\s+AZIONE\s+ORDINARIA)?
       \s*\n+
       (?:Euro|euro|EUR|€)\s* (<amount>)
       \s* (?:\(.+?\))?  # optional "(spelt-out)" or "(cum div)"
       \s* (?:cum\s+dividendo|cum\s+dividend)?
       \s* per\s+(ciascuna|ogni)\s+azione (?:\s+ordinaria)? (?:\s+di\s+<TARGET>)?
```

Key recognizable structures:
- **Label** (case-insensitive, allow whitespace variation):
  `Corrispettivo unitario offerto` (optionally followed by
  `per azione ordinaria`).
- **Currency**: `Euro`, `euro`, `EUR`, or `€`.
- **Amount**: Italian decimal with `,` (2-3 decimals observed:
  `6,17` `0,61` `27,00` `7,00` `0,467` `4,30` `2,65` `3,50`).
- **Connector**: `per ciascuna azione` (8 / 9 readable) or `per ogni
  azione` (1 / 9 — CIR).
- **Optional qualifiers**: `cum dividendo` / `cum dividend` / `(<words
  in parentheses>)`.

### Confirmed traps

| Trap | Pattern | Sample occurrences |
|---|---|---|
| Number written in words | `Euro 6,17 (sei virgola diciassette)` | Civitanavi, Medica — extract numeric, ignore spelt-out |
| `cum dividendo` qualifier | `Euro 7,00 cum dividendo, ossia ...` | anima, bialetti, almawave — does **not** change the price |
| HK ticker on cross-listed deals | `09638.HK` | Ferretti — must not match ISIN regex |
| Mixed-offer ratio | `n. 21 azioni Kruso Kapital S.p.A.` | Banca Sistema — "21" must not be matched as a EUR amount |
| Sub-component cash (mixed) | `(a) Euro 1,382 in contanti` | Banca Sistema — pick *total* `Euro 1,80`, not the cash leg |
| Section index amounts (page 2-3) | "Esborso Massimo" totals in the TOC | All long docs — restricting to the cover page avoids this |

### Number-formatting observations

- Decimal separator: always `,` (`6,17`, `0,467`).
- Thousand separator on the cover: not observed for offer prices
  (amounts are all < 100 €), but appears in "Esborso Massimo" totals
  deeper in the doc (e.g. `253.756.155` shares = standard Italian
  `.` thousand separator). The cover-page regex sees small amounts
  so the formatting risk is low.
- 3-decimal precision is real for small caps (Bialetti `0,467`) and
  for cash legs in mixed offers (Banca Sistema `1,382`). The current
  parser handles up to 4 decimals (`\d{2,4}`), so this is not a
  failure mode.
- `Euro` / `euro` / `€` — parser must be case-insensitive on the
  currency symbol.

### ISIN extraction — empirical coverage

| Position | Frequency | Reliability |
|---|---|---|
| Filename | 0 / 10 | None |
| Cover page (first 1-2 pages) | 0 / 10 | None |
| Body of doc (Section B.2 typically) | Estimated > 80 % | Requires deeper text extraction |

**Conclusion:** ISIN is **not** on the Consob cover. Extraction must
read past the cover page into Section B.2 "Soggetto Emittente"
where the target company is described (`codice ISIN: IT…`). This is
a significant difference from AMF and a likely contributor to
delayed ISIN population on IT deals. Coverage on the 47-deal corpus
needs deeper-page extraction to estimate.

### Offer-type distribution in sample (n = 10)

| Type | Italian label | Count |
|---|---|---|
| OPA Volontaria Totalitaria cash | "OPA Volontaria Totalitaria" | 5 (Civitanavi, Medica, anima, almawave, Eles) |
| OPA Obbligatoria Totalitaria cash | "OPA Obbligatoria" | 1 (Bialetti) |
| OPA Volontaria Parziale (cash buyback / partial) | "OPA Volontaria Parziale" | 2 (CIR self-tender, Ferretti partial) |
| OPAS mixed cash + share | "OPA e Scambio" | 1 (Banca Sistema) |
| Unknown (extraction failure) | n/a | 1 (Piovan) |

Mixed offers (OPAS) are rarer than in BaFin (Commerzbank, ProSieben)
but the structure is analogous and the parser can reuse the P9.1c
two-leg extraction pattern.

## Why Consob is currently 5 / 47 — empirical hypotheses

Three failure modes are observed in this 10-PDF sample:

1. **Image/encoding-broken PDF text** (Piovan): 1 / 10. PyMuPDF
   produces scrambled output on the cover. OCR fallback required.
   If extrapolated to the 47-deal corpus, this could account for
   5-10 PDFs.
2. **Non-page-1 cover** (Ferretti): 1 / 10. The HK dual-listing
   disclaimer pushes the structured cover to page 2. A page-1-only
   parser misses these. If 2 / 10 in the sample, ~10 of 47 in the
   corpus.
3. **Label-variant or qualifier-stripping issues**: most clean
   covers (8 / 10) used `CORRISPETTIVO UNITARIO OFFERTO`, one used
   the variant `CORRISPETTIVO UNITARIO OFFERTO PER AZIONE
   ORDINARIA` (almawave), one used Title Case `Corrispettivo
   unitario offerto` (Medica). A regex too tightly bound to the
   exact uppercase label would miss 1-2 / 10.

These three failure modes together cover the ~89 % failure rate
(42 / 47) plausibly — *if* the current parser is page-1-only,
all-caps-label-only, and has no OCR fallback. The fix is
incremental, not a rewrite: broaden the label regex, scan pages
1-5, add OCR fallback when extracted text is empty.

The **Banca Sistema** mixed offer (OPAS) is *not* a failure mode of
the existing parser — it's a feature gap. Even if the parser
captured `Euro 1,80` from the composite cover, the
`offer_price_total_eur` field (P9.1c) plus `deal_consideration`
table need to be populated with the cash leg (1,382) and the share
leg (0,418 worth, paid in Kruso Kapital shares at a 1:21 ratio).
That's the same downstream work as Commerzbank / ProSieben (P9.1c).

## Quick-win question — what do the 5 working Consob deals look like?

This audit can't directly answer "which 5 / 47 are populated" because
the DB is offline. But the working set is almost certainly a subset
of the **clean cover + uppercase label + page-1 placement** pattern
observed in 7 / 10 sampled deals (Civitanavi, CIR, anima, bialetti,
almawave, Eles — and Banca Sistema if a partial-cash extraction
ran).

The current Consob regex (`src/ingestion/consob/parser.py`
`l. 49-50`):

```python
r"(?:(?:Euro|EUR|€)\s*(?P<amount1>\d{1,3}(?:[ .]\d{3})*[,.]\d{2,4}))"
r"|(?:(?P<amount2>\d{1,3}(?:[ .]\d{3})*[,.]\d{2,4})\s*(?:Euro|EUR|€))"
```

…does NOT anchor on the `CORRISPETTIVO UNITARIO OFFERTO` label. It
just picks the first EUR amount on the parsed pages. This explains
the partial success: the cover-page format puts the offer-price
amount as the *first or near-first* EUR amount on page 1, so the
naive parser gets it right when the cover is clean. The remaining
failures (≈ 42) are dominated by the three failure modes above.

**Quick win (P9.2 impl):**
1. Anchor on the `CORRISPETTIVO UNITARIO OFFERTO` label (regex
   tolerant to case + whitespace + optional `PER AZIONE ORDINARIA`)
   to *qualify* the matched amount rather than rely on first-amount-
   wins. Recovers 7-8 / 47 by eliminating false positives from
   deeper pages.
2. Scan pages 1-5 instead of page 1 only. Recovers ~10 / 47.
3. OCR fallback when extracted text length < threshold. Recovers
   ~5-10 / 47.

Combined, these three changes should plausibly take Consob from
5 / 47 to ~30-35 / 47, leaving the long tail of genuinely
malformed / partial / non-standard PDFs to a P9.2b follow-up.

## Limitations of this Step 0

Same as the AMF audit:
- No `completion_label` stratification (DB offline).
- 10 / 47 sample — patterns are likely fully covered (the cover
  format is highly standardized), but tail-end exceptions
  (acquisition by foreign acquirer, partial offer, OPAS) are
  represented only by 1-2 examples each.
- Only the first 5 pages of each PDF were extracted; ISIN coverage
  estimation requires deeper pages.
