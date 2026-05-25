# P9.1a — Cluster A diagnosis: `offer_price = EUR 1.00` (par-value capture)

**Status:** diagnosis only — no fix in this commit. Validated against the 4
fixture PDFs in `tests/fixtures/p91a/`.

## TL;DR

The four deals stored at `offer_price = 1.00` are **not** a single hardcoded
fallback. Root cause: `_extract_price` returns the **first** EUR amount found in
the first 10 pages. For German *Stückaktien* that first amount is almost always
the per-share notional of share capital —
*"anteiliger Betrag am Grundkapital … von EUR 1,00"* — which BaFin templates
print **before** the actual offer price.

| deal | stored | true consideration | verdict |
|---|--:|---|---|
| Commerzbank (348) | 1.00 | 0.485 UniCredit shares, **no cash** | misparse (par value) — also Pattern B |
| Linus (1070) | 1.00 | **EUR 1.76** cash | misparse (par value) |
| infas (1079) | 1.00 | **EUR 6.80** cash | misparse (par value) |
| Philomaxcap (1080) | 1.00 | **EUR 1.00** cash | **CORRECT** (coincidence) — not a bug |

➡️ Cluster A = **3 true misparses + 1 false positive**. The "exact 1.00 = always
a fallback" hypothesis from Step 0 is **partially wrong**: Philomaxcap's offer is
genuinely EUR 1.00.

## Code path

- `_extract_price` — `src/ingestion/bafin/parser.py:192-202`
  → `m = _PRICE_RE.search(text)` returns the **first** match, unconditionally.
- `_PRICE_RE` — `src/ingestion/bafin/parser.py:81-85` — matches any
  `EUR X,XX` / `X,XX EUR`, with **no anchor** to the offer context and **no
  exclusion** of capital / par-value context.
- Call site — `extract_pdf_metadata` `src/ingestion/bafin/parser.py:139`
  (`price, currency = _extract_price(text)`).

Outcome is therefore **document-ordering dependent**: whichever of
"Grundkapital … EUR 1,00" vs "Geldleistung … EUR X,XX" appears first wins.

## Evidence (EUR matches in document order; parser uses #1)

**Linus (DE000A2QRHL6)**
- `#1` (used): *"…auf die einzelne Aktie jeweils entfallenden rechnerischen Anteil am **Grundkapital von EUR 1,00**…"* ← par value
- `#2` (ignored): *"…gegen Zahlung eines **Geldbetrags in Höhe von EUR 1,76** je zur Annahme eingereichter Aktie…"* ← **true offer**

**infas (DE0006097108)**
- `#1` (used): *"…mit einem anteiligen Betrag am **Grundkapital von je EUR 1,00** gegen eine Geldleistung in Höhe von…"* ← par value
- `#2` (ignored): *"…gegen eine **Geldleistung in Höhe von EUR 6,80** je zur Annahme eingereichter Aktie…"* ← **true offer**

**Commerzbank (DE000CBK1001)**
- `#1` (used): *"…Stückaktien der Commerzbank mit einem anteiligen Betrag am **Grundkapital … von jeweils EUR 1,00**…"* ← par value
- No cash offer exists at all — the consideration is a share swap
  (*"Gegenleistung von 0,485 Aktien der UniCredit S.p.A."*). See
  `p91a_pattern_mixed_diagnosis.md`.

**Philomaxcap (philomaxcap) — counter-example**
- `#1` (used): *"…Aktien ohne Nennwert der Philomaxcap AG gegen **Zahlung eines Geldbetrags von EUR 1,00 je Aktie**."* ← this **is** the offer
- `#3`: *"Gegenleistung EUR 1,00 je Aktie der Philomaxcap AG."* ← confirms
- Here the offer clause precedes the Grundkapital clause, so first-match is
  correct **and** the real price equals the par value (EUR 1.00). Coincidence,
  not robustness.

## Why the `< EUR 5` threshold cannot gate the fix

Philomaxcap proves a genuine sub-EUR-5 offer is indistinguishable from a
misparse **by value alone**. Any fix that "corrects" low values blindly would
corrupt Philomaxcap. → P9.1b must validate each suspect against an **external
reference price per ISIN**; the parser fix must not overwrite on magnitude.

## Fix hypothesis (not implemented)

Anchor extraction to the consideration clause: capture the amount in
`Geldleistung|Geldbetrag (in Höhe von)? EUR X[,.]XX je … Aktie`, and **reject**
any EUR match whose immediate context contains
`Grundkapital | anteiliger Betrag | Nennbetrag | rechnerischer Anteil`. Return
`None` (not first-match) when no consideration clause is found, so a missing
price is recorded as missing rather than as the par value.
