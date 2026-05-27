# P9.2 Step 0 — AMF manual extraction audit

**Goal.** Empirically characterize how `offer_price` + ISIN are presented in
AMF "Décisions & Informations" PDFs, to inform the P9.2 parser-hardening
brief. Sample size 10 PDFs, no DB-driven label stratification (Postgres not
running locally — year-folder used as a coarse proxy for status).

**Methodology.** First 2-5 pages of each PDF extracted via PyMuPDF
(`scripts/p92_dump_pdf_text.py`), then read in full by hand. Each entry
below records:
- the offer-price anchor text (verbatim, ±15 words of context),
- ISIN position (filename header / body / both),
- offer type (cash pure / cash multi-tranche / mixed alternative / share swap),
- traps: every other EUR amount that a naive `\d+[,.]?\d*\s*€` regex would
  match and that a parser MUST NOT pick as the offer price.

The 10 PDFs span 2016 → 2025 announcement dates so the corpus covers
formatting drift; year-folder distribution: 2 × 2022, 1 × 2023, 2 × 2024,
3 × 2025, 2 × 2026 (year-folder reflects ingestion year, not announcement).

## Per-deal extractions

### [1] `216C1735` — CEGID GROUP (2016, OPA cash, conformity decision)

- **Anchors found** (3 occurrences of the *real* offer price):
  - p1 l37 : "Claudius Finance S.à r.l. a acquis hors marché … 3 470 156
    actions CEGID GROUP **au prix unitaire de 61,00 € par action**"
    *(this is the block purchase price, equal to the offer price)*
  - p1 l49 : "L'initiateur s'engage irrévocablement à acquérir … 5 654 839
    actions CEGID GROUP non détenues par lui ou par Claudius Finance
    S.à r.l. … **au prix de 61,00 € par action** (dividende détaché)"
  - p3 l150 : "**au prix par action de 61 euros** (dividende 2015 détaché)"
- **Traps:**
  - p1 l53 : "**au prix de 44,25 € par BAAR**" — BAAR are warrants
    (bons d'acquisition d'actions remboursables), *not* shares.
  - p1 l56 / p2 l97 : "**complément de prix de 1,25 €** sera versé" —
    price supplement contingent on retrait obligatoire, not the headline
    offer price.
  - footnote 2 l62 : "**1,25 euro par action**" — describing the dividend
    paid by CEGID on 13/05/2016.
- **ISIN:** `FR0000124703` — present in filename (`216C1735-FR0000124703-OP019-A06`)
  and reprinted at the top of pages 2 and 3. 100 % extractable.
- **Offer type:** cash pure, but **with a parallel BAAR offer at a
  different price.** A parser must qualify the matched amount with
  "par action" and reject "par BAAR".

### [2] `219C0051` — TESSI (2019, OPA simplifiée cash, deposit notice)

- **Anchor (1 occurrence):**
  - p1 l45 : "L'initiateur s'engage irrévocablement à acquérir la totalité
    des actions TESSI qu'il ne détient pas … **au prix unitaire de
    160 euros** (le dividende exceptionnel et l'acompte sur dividende
    envisagés pour un montant total de 42,70 € par action étant attachés)"
- **Traps:**
  - p1 l46 : "**42,70 € par action**" — describes the dividend attached
    to the offer, *not* the offer price. Critical trap: same suffix
    "par action" as the offer anchor. The discriminator is the verb
    ("s'engage irrévocablement à acquérir … au prix" vs "dividende … pour
    un montant total de").
- **ISIN:** `FR0004529147` — filename + header. 100 % extractable.
- **Offer type:** cash pure.
- **Formatting note:** "**160 euros**" (no decimals, plural "euros"); the
  parser must accept integer prices.

### [3] `223C0044` — SERMA GROUP (2023, response note, no headline price)

- **Anchor:** none. The PDF is a "projet de note en réponse" filed by
  the target's board, complementary to the original deposit notice
  `222C2665` (December 2022). It does not restate the offer price.
- **Traps:** none.
- **ISIN:** `FR0000073728` — filename + header. 100 % extractable.
- **Offer type:** N/A (this PDF type carries metadata, not the price).
- **Implication:** AMF publishes 3-5 PDFs per deal (deposit notice,
  response note, conformity decision, closing notices). The parser
  must (a) recognize which PDF *types* carry the price and (b)
  acknowledge that the others legitimately don't. Empty extraction on
  a response note is not a bug.

### [4] `224C0830` — TIPIAK (2024, OPA simplifiée cash, deposit notice)

- **Anchors (2 occurrences):**
  - p1 l45 : "L'initiateur s'engage irrévocablement à acquérir **au prix
    de 88 € par action** la totalité des actions TIPIAK qu'il ne détient
    pas"
  - p2 l77 : "retrait obligatoire visant les actions TIPIAK non
    présentées à l'offre, **au prix de 88 € par action**"
- **Traps:**
  - p1 l40 : "L'initiateur a acquis … 712 493 actions TIPIAK …
    **au prix unitaire de 82 €**" — block purchase price 82 €, *lower
    than* the offer price 88 €. This is the most common trap pattern:
    the initiator bought the controlling block at one price and is
    offering the rest of the market at a (typically higher) price.
    Same anchor token "prix unitaire" — the discriminator is the verb
    ("a acquis" vs "s'engage à acquérir").
  - p1 l53 : "**dans la limite de 150 € par dossier**" — transaction
    fee cap.
- **ISIN:** `FR0000066482` — filename + header. 100 % extractable.
- **Offer type:** cash simplifié.

### [5] `224C0915` — TRAVEL TECHNOLOGY INTERACTIVE (2024, OPA simplifiée cash, deposit notice)

- **Anchors (2 occurrences):**
  - p1 l54 : "L'initiateur s'engage irrévocablement à acquérir, **au prix
    unitaire relevé de 2,85 €** (contre 2,34 € initialement annoncé dans
    le communiqué du 21 décembre 2023)"
  - p2 l77 : "retrait obligatoire … en contrepartie d'une
    **indemnisation unitaire de 2,85 €**"
- **Traps:**
  - p1 l42 : "**au prix unitaire de 2,34 euros par action**" — block
    purchase price (and superseded initial offer price). Note the
    parenthetical "(contre 2,34 € initialement annoncé)" in the real
    anchor — the parser must NOT take 2,34 as the price, even though
    it appears very close to "prix unitaire".
  - p1 l43 : "**au prix unitaire de 1,27 euro par BSA**" — warrant price.
  - p1 l44 : "**au prix unitaire de 0,50 euro**" — warrant exercise
    price (no "par BSA" suffix in this sentence).
- **ISIN:** `FR0010383877` — filename + header. 100 % extractable.
- **Offer type:** cash simplifié.
- **New anchor variant:** "**au prix unitaire relevé de X €**" — the
  "relevé" qualifier marks a raised offer; the parser should accept
  optional adjectives between "unitaire" and "de".
- **New anchor variant:** "**indemnisation unitaire de X €**" — used
  for the retrait-obligatoire indemnification leg, omits "par action".

### [6] `225C0021` — NEOEN (2025, OPA simplifiée Brookfield, deposit notice)

- **Anchors (1 occurrence for shares, 2 for convertibles):**
  - p1 l53 : "L'initiateur s'engage irrévocablement à acquérir au prix
    de : **39,85 € par action**, la totalité des 70 713 338 actions
    NEOEN qu'il ne détient pas"
  - p2 l79 : "retrait obligatoire … aux **prix de l'offre**" (no
    explicit number; references the offer's existing prices).
- **Traps:**
  - p1 l42 : "**au prix unitaire de 39,85 €**" — block purchase from
    Impala, FSP, etc., equal to the offer price. *Happens to match*
    but again the verb is "a acquis", not "s'engage à acquérir".
  - p1 l58 : "**48,14 € par océane 2020**" — OCEANE 2020 convertible
    price.
  - p1 l60 : "**101 382,00 € par océane 2022**" — OCEANE 2022 price.
    **Critical formatting trap:** `101 382,00 €` uses a non-breaking
    or regular space as the thousands separator. Naive regex
    `\d{1,3}(?:[.]\d{3})*,\d{2}` would fail; the parser must accept
    `\s` as a thousands separator. Also: this is the largest amount
    in the entire document, so a "pick the biggest EUR amount"
    heuristic would be catastrophically wrong.
  - p1 l64 : "**150 € par dossier**" — fee cap.
- **ISIN:** `FR0011675362` — filename + header. 100 % extractable.
- **Offer type:** cash simplifié, **multi-tranche** (shares + 2 series
  of convertibles, each priced separately). The parser must select
  the *share* tranche (`par action`) and ignore `par océane`.

### [7] `225C0741` — FINANCIERE MONCEY (2025, OPA alternative de retrait, conformity decision)

- **Anchors — this is a mixed offer with alternative branches:**
  - p1 l48 : "**133 € par action FINANCIERE MONCEY apportée**
    (la branche « numéraire »)" — cash branch.
  - p1 l50 : "**5,67 actions Universal Music Group N.V. (« UMG »)4
    remises pour 1 action FINANCIERE MONCEY apportée** (la branche
    « titres »)" — share-swap branch.
  - p1 l60 : "moyennant une indemnisation exclusivement en numéraire
    égale au **prix d'offre de 133 € par action FINANCIERE MONCEY**" —
    forced cash for the retrait obligatoire.
- **Traps:** none (a clean alternative-branch structure; no block
  pre-purchases at different prices).
- **ISIN:** `FR0000076986` — filename + header. Also a *second* ISIN
  in footnote 4 (UMG: `NL0015000IY2`) — the acquirer's ISIN; the
  parser must extract the *target* ISIN, not the first ISIN encountered.
- **Offer type:** **mixed alternative** — French equivalent of the
  BaFin "Geldleistung + Gewährung von Aktien" structure (P9.1c). The
  same two-leg structured-extraction pattern applies, with the
  language anchors:
  - cash leg:  `X € par action <Target> apportée` / `branche numéraire`
  - share leg: `X actions <Acquirer> remises pour 1 action <Target>
    apportée` / `branche titres`

### [8] `225C0921` — M2I (2025, OPA simplifiée cash, conformity decision)

- **Anchors (2 occurrences):**
  - p1 l52 : "L'initiateur s'engage irrévocablement à acquérir,
    **au prix unitaire de 8,50 €**, la totalité des actions M2I
    existantes qu'il ne détient pas"
  - p2 l77 : "retrait obligatoire … en contrepartie d'une
    **indemnisation unitaire de 8,50 €**"
- **Traps:**
  - p1 l37 : "la société Abilways a acquis … **au prix unitaire de
    8,50 €**, un bloc majoritaire composé de 3 458 673 actions M2I" —
    block purchase price equal to offer price. Verb is "a acquis",
    not "s'engage".
- **ISIN:** `FR0013270626` — filename + header.
- **Offer type:** cash simplifié.

### [9] `225C2081` — SOCIETE DE TAYNINH (2025, OPA simplifiée cash, deposit notice)

- **Anchor (1 occurrence):**
  - p2 l74 : "L'Initiateur s'engage irrévocablement à acquérir, **au
    prix unitaire de 0,11€**, la totalité des actions de la société
    SOCIETE DE TAYNINH existantes non détenues par le Concert"
- **Traps:**
  - p1 l42 : "**pour un prix de l'ordre de 0,11 euro par action**" —
    block purchase price, equal to offer (note "de l'ordre de" hedge).
  - p1 l45 + p1 l47 : "**1,96 euro par action**" — *exceptional
    distribution* paid 31/10/2025, detached before the offer. A naive
    "first amount near 'euro par action'" heuristic would grab this
    (1,96 € > 0,11 €).
- **ISIN:** `FR0000063307` — filename + header.
- **Offer type:** cash simplifié, post-distribution. **Important:**
  exceptional distributions are a recurring trap, distinct from
  ordinary dividends and from price supplements.
- **Note:** `0,11€` (no space before `€`) — the parser must accept
  both `0,11€` and `0,11 €` (and `0.11 €`, etc.).

### [10] `225C2156` — PRODWARE (2025, offre publique de retrait cash, conformity decision)

- **Anchors (2 occurrences):**
  - p1 l42 : "L'initiateur s'engage irrévocablement à acquérir, **au
    prix unitaire de 28 € par action**, la totalité des actions
    PRODWARE qu'il ne détient pas"
  - p2 l80 : "retrait obligatoire … en contrepartie d'une
    **indemnisation de 28 € par action PRODWARE**"
- **Traps:** none (PRODWARE is a clean OPR with no BSAANE pricing
  inline in this PDF; the BSAANE warrants are mentioned but not priced
  in the first two pages).
- **ISIN:** `FR0010313486` — filename + header.
- **Offer type:** cash OPR (offre publique de retrait, no preliminary
  block).

## Summary of patterns discovered

### Confirmed offer-price anchors (in observed frequency order)

1. `s'engage irrévocablement à acquérir … au prix unitaire de <amount> €
   [par action]` — 6 / 10 PDFs.
2. `au prix [unitaire] de <amount> € par action` — 5 / 10 PDFs (overlaps with #1).
3. `indemnisation [unitaire] [de] <amount> € [par action]` — 4 / 10 PDFs
   (retrait obligatoire variant; often restates the offer price).
4. `<amount> € par action <Target> apportée` — 1 / 10 PDFs (mixed
   alternative branch — MONCEY).
5. `<amount> euros` (no `€`, plural) — 1 / 10 PDFs (TESSI 2019).

Common shape: `[s'engage à acquérir|indemnisation] … (prix|au prix) (unitaire )?(relevé )?de <amount> (€|euros?)[\s,]*(par action|par action <TARGET>( apportée)?)?`.

### Confirmed traps (must be excluded)

| Trap | Pattern | Occurrences |
|---|---|---|
| Block purchase price | `a acquis … (un bloc|N actions) … au prix unitaire de <amount> €` | 5 / 10 (CEGID, TIPIAK, Travel Tech, M2I, NEOEN, TAYNINH) |
| Complément de prix | `complément de prix de <amount> €` | 1 / 10 (CEGID) |
| Dividend / exceptional distribution | `dividende … <amount> € par action`, `Distribution … <amount> euro par action` | 2 / 10 (TESSI, TAYNINH) |
| Transaction fees | `frais … dans la limite de <amount> € par dossier` | 2 / 10 (TIPIAK, NEOEN) |
| Convertible/warrant prices | `<amount> € par (BAAR\|BSA\|océane)` | 3 / 10 (CEGID, Travel Tech, NEOEN) |
| Acquirer ISIN | second ISIN belonging to the buyer | 1 / 10 (MONCEY footnote 4) |

**Number-formatting subtraps:**
- French thousand separator is a space (or non-breaking space):
  `101 382,00 €`. Naive `\d{1,3}(?:\.\d{3})*,\d{2}` regex misses this.
  Use `\d{1,3}(?:[\s .]\d{3})*,\d{2,4}` or strip whitespace before
  parsing.
- Decimal separator is always `,` in the EUR amount (`8,50`, `2,85`),
  never `.`.
- `€` may be glued (`0,11€`) or separated (`0,11 €`); allow `\s*€`.
- "euros" (plural) and "euro" (singular) both appear, alongside `€`.

### Discriminating verbs (what distinguishes the real offer from traps)

- **Offer price verb:** `s'engage [irrévocablement] à acquérir`
- **Block trap verb:** `a acquis`, `a acquis hors marché`, `s'est engagé
  à acquérir … un bloc`
- **Dividend trap noun:** `dividende`, `distribution`, `acompte sur
  dividende`, `complément de prix`
- **Fee trap noun:** `frais (de négociation|de courtage)`, `par dossier`
- **Convertible trap noun:** `par BAAR`, `par BSA`, `par océane`, `par
  bon`

### ISIN extraction — empirical coverage

| Position | Frequency | Reliability |
|---|---|---|
| Filename prefix (`<amf_ref>-<ISIN>-OP…-…`) | 10 / 10 | Highest |
| First-page document header (line 2-4) | 10 / 10 | Highest |
| Reprinted on each subsequent page header | 10 / 10 | High |
| Body of text | varies | Medium |

**Conclusion:** the AMF reference filename itself carries the ISIN
in 100 % of the sampled corpus. The parser can extract ISIN by
filename pattern alone (`^\d{3}C\d{4}-([A-Z]{2}[A-Z0-9]{9}[0-9])-`),
no PDF parsing required. The Luhn check on the trailing digit can
serve as validation.

### Offer-type distribution in sample (n = 10)

| Type | Count | Notes |
|---|---|---|
| Cash pure / cash simplified | 8 | Includes one multi-tranche (NEOEN: shares + 2 convertible series) |
| Mixed alternative (cash OR shares) | 1 | MONCEY — same shape as BaFin Geldleistung/Gewährung |
| Share swap pure | 0 | Not observed in sample; should appear in OPE deals (`offre publique d'échange`) |
| N/A — response note / supplementary | 1 | SERMA — no price restated |

Extrapolation to the 730-deal corpus is uncertain (sample is small and
not stratified by completion_label), but the qualitative finding is:
**cash dominates AMF**, mixed offers exist (rarer than BaFin), share
swaps are likely a minority.

## Why FR is currently 0 / 730 — hypotheses to confirm in P9.2 impl

1. Current `src/ingestion/amf/parser.py` (l. 16 docstring: "phase 2 only
   does *basic* extraction; deep section parsing lands in phase 6")
   never received the offer-price regex hardening that BaFin got in
   P9.1a. The "phase 6" reference seems to have been deprioritized.
2. The parser likely runs on *every* AMF PDF type, including
   response notes and closing notices that legitimately don't carry
   the price — flagging zero of them.
3. The block-purchase-vs-offer trap (5 / 10 in sample) means even a
   regex on `prix unitaire de \d+,\d+ €` would pick the wrong value
   in roughly half the cash cases. A verb-based discriminator
   (`s'engage … à acquérir`) is needed.
4. French number formatting (space thousands separator) might break
   the inherited Italian/German regex even when a match exists in text.

These are hypotheses for the P9.2 impl brief — Step 0 does not
verify them against the running parser.

## Limitations of this Step 0

- **No `completion_label` stratification.** Postgres is not running
  locally; the 5-closed / 3-failed / 2-announced split was replaced
  by a year-folder split. The discovered patterns are status-agnostic
  (they're linguistic, not outcome-correlated), so the lack of
  stratification does not invalidate the catalogue, but it does mean
  *we cannot estimate how many of the 730 FR deals match each
  pattern* without re-running this on a labelled sample.
- **No size stratification.** Sample spans small caps (TAYNINH 0,11 €,
  Travel Tech 2,85 €) through mid caps (CEGID 61 €, TESSI 160 €,
  TIPIAK 88 €, PRODWARE 28 €) up to large (NEOEN 39,85 € × 152 M shares,
  MONCEY 133 €). Reasonable coverage by accident, not by design.
- **Sample is 10 PDFs out of 730.** A handful of rarer patterns
  (share-swap pure, OPRA share buybacks, garantie de cours) may exist
  in the corpus and not in this sample.
