# BaFin Angebotsunterlagen — source mapping (Phase 5 Step 0)

**Date:** 2026-05-19
**Probed by:** `artifacts/phase-05/step0_probe.py` + `step0_probe2.py`
**Fixtures:** `tests/fixtures/bafin/{angebotsunterlagen-listing.html, wrapper-commerzbank.html, sample_*.pdf}`

---

## TL;DR

| Item | Value |
|---|---|
| **Anti-bot** | **None.** Direct `httpx` returns 200 on listing, wrappers and PDFs with a desktop UA + `Accept-Language: de-DE`. |
| **ScrapingBee budget** | **0 credits.** No proxy needed. |
| **Listing structure** | Single monolithic `<table class="data">`, no pagination, **241 rows spanning 2016–2026**. |
| **Recent volume** | 2026: 2 / 2025: 20 / 2024: 32 — **12-month window ≈ 22–25 rows** (matches Consob). |
| **PDF URL pattern** | **Deterministic** from wrapper URL: `path/foo.html?nn=…` → `path/foo.pdf?__blob=publicationFile&v=1`. Wrapper fetch is optional. |
| **Validated** | 3 / 3 sampled PDFs returned valid `%PDF-` bytes (1.5–3.3 MB each). |

## ⚠️ Important URL correction vs Phase-5 brief

The brief lists `https://www.bafin.de/SharedDocs/Veroeffentlichungen/DE/Liste/WPUeG/li_angebotsunterlagen_wpueg_14.html` — this URL **returns 404** (BaFin retired the `SharedDocs/Veroeffentlichungen/...` legacy path).

**Working URL:**
```
https://www.bafin.de/DE/die-bafin/publikationen-daten/datenbanken-uebersichten/WPUeG/angebotsunterlagen/angebotsunterlagen_node.html
```

The list of "Veröffentlichte Angebotsunterlagen (§ 14 WpÜG)" now lives under `die-bafin/publikationen-daten/datenbanken-uebersichten/WPUeG/...`. Confirmed via WebSearch + direct httpx probe (200 OK, 222 KB HTML).

## HTTP request policy

| Field | Value |
|---|---|
| Method | `GET` (no auth) |
| User-Agent | `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ... Chrome/147 Safari/537.36` |
| Accept-Language | `de-DE,de;q=0.9,en;q=0.7` *(probably not strictly required — needs A/B test before assuming)* |
| Accept | `text/html,application/xhtml+xml,...` |
| Rate limit observed | comfortable (no throttling on 3 sequential probes); proposed client policy: **1 req/s + jitter** to stay polite (reuse `src/ingestion/amf/rate_limiter.py`) |
| Retries | exponential backoff 1/2/4 s on `429`/`5xx`/`TransportError` (reuse `retry_with_backoff`) |
| Timeout | 30 s |

## Listing HTML structure

Single `<table class="data">`, 1 header row + 240 data rows. Each `<tr>` has exactly 5 `<td>`:

| # | Column | Content example | Notes |
|---|---|---|---|
| 0 | Bieter | `UniCredit S.p.A., Italien` | Free text, comma-separated city/country |
| 1 | Zielgesellschaft | `COMMERZBANK Aktiengesellschaft, Frankfurt am Main` | Free text |
| 2 | ISIN | `DE000 CBK1001` | **Spaces inside the ISIN** — must be normalised (`re.sub(r"\s+", "", isin)`) before storage |
| 3 | Angebotsunterlage | `<a href="…/commerzbank.html?nn=151388">Übernahmeangebot</a>` | Link **text** = offer type; `href` = wrapper URL |
| 4 | Veröffentlichung am | `05.05.2026` | DD.MM.YYYY |

**BeautifulSoup selector:**
```python
soup = BeautifulSoup(html, "lxml")
table = soup.find("table", class_="data")
rows = table.find_all("tr")[1:]  # skip header
for tr in rows:
    tds = tr.find_all("td")
    if len(tds) != 5:
        continue
    bieter = tds[0].get_text(" ", strip=True)
    target = tds[1].get_text(" ", strip=True)
    isin   = re.sub(r"\s+", "", tds[2].get_text(strip=True))
    a      = tds[3].find("a")
    otype  = a.get_text(" ", strip=True)
    href   = a["href"]
    date_str = tds[4].get_text(strip=True)
```

## Pagination

**None.** The page is monolithic. `gtp=` link count = 0; no `.pagination` / `.seite` nav class. The single-page model is comfortable: 241 rows / 222 KB / 1 GET.

## Wrapper page → real PDF

Each `<a>` in the `Angebotsunterlage` column points to an HTML wrapper (`…/{slug}.html?nn=151388`, ~99 KB) that re-displays the deal in a styled BaFin layout. The wrapper contains exactly **one** PDF link with the pattern:

```
https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/{slug}.pdf?__blob=publicationFile&v=1
```

The PDF URL is **deterministic from the wrapper URL** — replace `.html?nn=…` with `.pdf?__blob=publicationFile&v=1`. **This means we can skip the wrapper fetch in the happy path** and go straight from listing → PDF, saving 1 HTTP round-trip per deal. The wrapper fetch becomes a fallback only when the deterministic URL 404s (e.g., versioned `v=2` on amended documents).

**Implementation rule:** try deterministic URL first; fall back to wrapper-scrape only on 404.

### Validated PDF samples (3/3 success)

| Bieter → Target | PDF URL | Bytes | Magic |
|---|---|---|---|
| UniCredit → Commerzbank | `commerzbank.pdf?…&v=1` | 3 255 699 | ✅ |
| Worthington → Klöckner & Co | `kloeckner-co-se-2.pdf?…&v=1` | 1 485 198 | ✅ |
| Zest Bidco → PSI Software | `PSI_Software.pdf?…&v=1` | 1 539 037 | ✅ |

## Offer-type taxonomy (full distribution, 241 rows)

The link text in column 3 is the **legal offer type**. Found 11 distinct values:

| Italian narrative | Count | % | German law mapping |
|---|---:|---:|---|
| Übernahmeangebot | 111 | 46 % | §29 WpÜG voluntary takeover targeting control |
| Delisting-Erwerbsangebot | 50 | 21 % | §39 BörsG delisting acquisition |
| Pflichtangebot | 29 | 12 % | §35 WpÜG mandatory (post-control) |
| Delisting-Übernahmeangebot | 16 | 7 % | Delisting + takeover (combined) |
| Teilerwerbsangebot | 11 | 5 % | Partial voluntary acquisition |
| Untersagung | 9 | 4 % | **Prohibition / refusal** — not an offer |
| Delisting-Pflichtangebot | 7 | 3 % | Delisting + mandatory |
| Delisting-Rückerwerbsangebot | 3 | 1 % | Delisting buyback |
| Erwerbsangebot | 3 | 1 % | Simple voluntary acquisition (<30 %) |
| Pflichtangebot / Erwerbsangebot | 1 | <1 % | Hybrid edge case |
| Erwerbsangebot Änderung | 1 | <1 % | Amendment to prior Erwerbsangebot |

## ⚠️ Decision needed before coding — canonical `deal_type` enum extension

The existing `deal_type_enum` (migration 0004, set up for FR + IT) has **no value for delisting-style offers** — and **76 of 241** BaFin rows (32 %) are delisting variants.

Three options to surface to the user:

| Opt | Approach | Pros | Cons |
|---|---|---|---|
| **A** | **New migration 0007** adding `delisting_offer` to `deal_type_enum`. Map all 4 delisting-* German variants → `delisting_offer`. | Clean, accurate, future-proof for IT/FR delistings too. | Touches enum (irreversible Postgres `ALTER TYPE ADD VALUE` — needs a documented downgrade strategy or a `DROP/CREATE` shuffle). |
| **B** | **Shoehorn** delisting-Übernahmeangebot → `opa_volontaire_totalitaria`, delisting-Pflichtangebot → `opa_obligatoire`, delisting-Erwerbsangebot → `opa_volontaire_parziale`, store the delisting flag in `events.raw_payload.is_delisting`. | No migration. | Lossy — querying "all delistings" requires JSONB extraction across phases. |
| **C** | **Add a `subtype` column** to `deals` (nullable, free text) that captures the raw German narrative. Map main offer to existing enum, keep delisting nuance in `subtype`. | Most flexible, still queryable. | Bigger migration. Schema sprawl. |

**Recommendation: Option A.** Aligns with the strict-typed approach used since Phase 1. A `delisting_offer` value will be needed eventually for IT/FR too (Italian Consob has `OPSC` delisting variants we currently fold into `opas`). Migration is small (~10 lines).

Also: `Untersagung` (9 rows) are **regulatory prohibitions, not offers** — **filter at discovery layer** (don't ingest). Document as a non-deal event in phase 6-7 if needed.

## German `deal_type` mapping table (proposed, pending Option-A decision)

| German narrative | Canonical enum |
|---|---|
| Übernahmeangebot | `opa_volontaire_totalitaria` |
| Pflichtangebot | `opa_obligatoire` |
| Erwerbsangebot | `opa_volontaire_parziale` *(or new `voluntary_minority`?)* |
| Teilerwerbsangebot | `opa_volontaire_parziale` |
| Delisting-Erwerbsangebot | **`delisting_offer`** (new) |
| Delisting-Übernahmeangebot | **`delisting_offer`** (new) |
| Delisting-Pflichtangebot | **`delisting_offer`** (new) |
| Delisting-Rückerwerbsangebot | **`delisting_offer`** (new) |
| Pflichtangebot / Erwerbsangebot | `opa_obligatoire` (treat as mandatory; rare hybrid) |
| Erwerbsangebot Änderung | parent row's type (it's an amendment); track as event `filing_bafin_amendment` in phase 7 |
| Untersagung | **filter out** at discovery |

## Dedup key proposal

BaFin does not expose a public `BaFin-NN-####` reference. Two viable approaches:

| Key | Example | Notes |
|---|---|---|
| `BAFIN-{pdf_slug}` | `BAFIN-commerzbank` | Matches Consob pattern. Risk: slug collisions for multiple deals on same target (Klöckner has `-2` suffix already — BaFin handles this internally). |
| `BAFIN-{ISIN-no-spaces}-{YYYYMMDD}` | `BAFIN-DE000CBK1001-20260505` | Robust against slug collisions, stable, parseable. **Recommended.** |

## Storage layout (proposed)

```
data/pdfs/de/{YYYY}/BAFIN-{ISIN}-{YYYYMMDD}.pdf
```

Atomic write via `tempfile.mkstemp` + `os.replace` (reuse `src/ingestion/consob/fetcher.py` pattern).

## Architecture summary (vs Consob)

| Aspect | Consob (IT) | BaFin (DE) |
|---|---|---|
| Listing access | ScrapingBee (Radware blocks direct) | **Direct httpx (free)** |
| Listing pages to fetch | 1 per 50 rows, paginated | **1 monolithic page** |
| PDF access | Direct httpx (recent) + ScrapingBee fallback (legacy) | **Direct httpx, all years** |
| Wrapper page step | n/a (direct PDFs) | Optional (deterministic URL pattern) |
| Anti-bot | Radware Bot Manager | **None observed** |
| Monthly credits estimate | ~30–90 (incremental tick) | **0** |

## Tech debt opened in Step 0

| # | Item | Severity | Owner |
|---|---|---|---|
| 1 | `deal_type_enum` lacks `delisting_offer` — 32 % of BaFin entries are delisting | **medium** | **decision required THIS phase** (migration 0007 if Option A) |
| 2 | `Untersagung` rows are regulatory prohibitions, not offers — filter at discovery (don't ingest as deals) | low | phase 5 (implemented at discovery) |
| 3 | `Erwerbsangebot Änderung` (amendments) link to prior deals — currently no `parent_deal_id` column. Capture as `events.raw_payload.amendment_for=<slug>` in phase 5, structural fix in phase 7. | low | phase 7 |

## STOP — awaiting user validation before coding

Per Phase-5 brief Step-0 protocol:

> **Stop after Step 0. Wait for user validation of the source mapping and architecture decision (direct httpx vs ScrapingBee) before coding.**

**Two decisions needed:**

1. ✅ / ❌ **Source mapping accepted** as documented above (URL correction, taxonomy, dedup key, storage layout, no ScrapingBee).
2. **Enum decision**: Option **A** (migration 0007 add `delisting_offer`) / **B** (shoehorn) / **C** (subtype column).

Once both received, Steps 1–9 can run (refactor SB client to core, discovery, fetcher, parser, service, poller, tests, live backfill, docs).
