# Data sources — provenance, rate limits, storage layout

Each ingestion module documents here:
- the upstream URL(s) and protocol
- the rate-limit policy applied client-side
- the User-Agent we send
- the dedup strategy
- the on-disk storage layout for any downloaded artifacts
- the operational caveats (latency, holidays, redesigns, etc.)

---

## AMF — Autorité des Marchés Financiers (FR) — phase 2 (RSS) + phase 3 (BDIF) ✅

### BDIF API (phase 3 — authoritative)

| Item | Value |
|---|---|
| Search endpoint | `GET https://bdif.amf-france.org/back/api/v1/informations` |
| Document endpoint | `GET https://bdif.amf-france.org/back/api/v1/documents/{path}` |
| Auth | none (public API, but client must look like a desktop browser) |
| Pagination | `From` (offset) + `Size` (page size, tested up to 100) |
| M&A filter | `typesInformation=OPA` + `typesDocument=NotesEtAutresInformations` |
| Rate limit observed | comfortably ≥ 1 req/s; we apply 1 req/s + jitter to be polite |
| Reverse-engineering notes | `docs/research/bdif-api-reverse-engineering.md` |

Mapping from `typesOperation` to canonical `deal_type` enum lives in
`src/ingestion/amf/bdif_api.py::OPERATION_TO_DEAL_TYPE`.

### RSS Communiqués (phase 2 — signal-only)


### Endpoints

| Resource | URL pattern |
|---|---|
| RSS feed (M&A decisions) | `https://www.amf-france.org/fr/flux-rss/display/23` |
| Detail page | `https://www.amf-france.org/fr/actualites-publications/decisions-et-informations-financieres/AMF-YYYY-X-NNNN` |
| BDIF PDF | `https://bdif.amf-france.org/back/api/v1/documents/{YYYY}/{REF}/{HASH64}.pdf` |

`{HASH64}` is a per-document opaque identifier (not predictable). We always discover it by scraping the detail page HTML rather than constructing the URL ourselves.

### HTTP request policy

- **Method**: `GET` (no auth)
- **User-Agent**: `EDE-Bot/0.1 (research; contact via repo)` (env: `USER_AGENT`)
- **Accept-Language**: `fr-FR,fr;q=0.9` — **required**; AMF/Akamai returns 403 without it
- **Rate limit**: 1 req/s (env: `POLLER_AMF_RATE_PER_SECOND`) + 0–200 ms positive jitter
- **Retries**: exponential backoff (1 s, 2 s, 4 s) on `429`, `500`, `502`, `503`, `504`, and any `httpx.TransportError`
- **Timeout**: 30 s end-to-end per request
- **Follow redirects**: yes

### Scope filter

Regex applied to RSS title (and summary as fallback), case-insensitive:

```
(offre publique | garantie de cours | note d'information | OPA | OPE | OPRA | OPR)
```

### Polling cadence

`APScheduler` interval job, default **15 min** (env: `POLLER_AMF_INTERVAL_MINUTES`). `max_instances=1`, `coalesce=true` so a slow run never overlaps with the next tick.

### Dedup

Primary key: `(juridiction='FR', regulator_ref)` — the unique constraint on `deals`. `regulator_ref` is extracted from the RSS title/link via `\bAMF-\d{4}-[A-Z]-\d{3,5}\b`. If no canonical ref is present, we synthesise `AMF-SYN-{sha256(title|published_date)[:24]}` so the constraint still holds.

`upsert_deal()` does a single read-then-insert; a second pass on the same RSS item skips silently and does NOT emit a duplicate `filing_amf` event.

### On-disk storage

PDFs land atomically (temp + `os.replace`) under:

```
${DATA_DIR}/pdfs/fr/{year}/{regulator_ref}.pdf
```

`DATA_DIR` defaults to `./data` on local Windows dev and is set to `/app/data` inside Docker (bind-mounted to `./data` on the host).

Re-downloading a previously-cached file is a no-op (early return on `path.exists() && size > 0`).

### Known caveats

1. **Detail page is a JS-heavy SPA.** Our regex looks for the BDIF URL in the raw HTML; if AMF migrates to client-side rendering of the document list, the scraper breaks silently (no exception, just `discover_bdif_url() → None`). Mitigation: monitoring will alert on `pdf_failed` counter rising.
2. **Akamai may rate-limit aggressively.** The 1 req/s + jitter is intentionally conservative; raise only with explicit verification.
3. **RSS frequency is irregular.** AMF often clusters publications late afternoon Paris time. The 15-min interval is a compromise; not worth tightening.
4. **Holidays.** French public holidays + August lull → expect days with zero new items.

### Live operations

```bash
# Trigger an ad-hoc poll (local dev, against the real RSS)
python scripts/amf_run_once.py
# Phase-8 CLI will expose:
#   python -m src.cli amf poll --once

# Inspect storage
ls data/pdfs/fr/2026/
```

### Phase 3 routing — BDIF authoritative, RSS signal-only

After the phase-2 live backfill showed `display/23` is the wrong feed for M&A documents, phase 3 introduces a **second** ingestion path targeting BDIF directly. The two paths now have distinct responsibilities:

| Source | Endpoint | Creates `Deal`? | Downloads PDF? | Emits `filing_amf` event? |
|---|---|---|---|---|
| **BDIF** (authoritative) | `GET /back/api/v1/informations` + `/back/api/v1/documents/...` | ✅ yes (real `numero`, no synthetic) | ✅ yes (atomic write) | ✅ yes (`source=bdif`, `has_document=true`) |
| **RSS `display/23`** (signal-only) | `https://www.amf-france.org/fr/flux-rss/display/23` | ❌ never | ❌ never | ✅ yes ONLY when the RSS item's canonical ref matches an existing BDIF deal (`source=rss_display_23`, `has_document=false`) |

This eliminates the phase-2 false-positive noise: communiqués that don't link to any BDIF document no longer create deal rows. They're silently logged as `amf.rss.skipped.unmatched` and dropped.

### Phase 2 tech debt — CLOSED 2026-05-13

The two items recorded in phase 2 are resolved by the `BdifPoller`:

1. **Synthetic `regulator_ref` (`AMF-SYN-*`)** — replaced by the real BDIF `numero` (e.g. `226C0644` for Fnac Darty). Live backfill on 60 items returned 0 synthetic refs.
2. **0 PDFs downloaded** — the BDIF API exposes a `documents[].path` field that constructs the canonical PDF URL deterministically. Live backfill downloaded 60/60 PDFs (37 in 2025, 23 in 2026) with zero failures.

Full live-backfill log: `artifacts/phase-03/bdif-backfill.txt`. API reverse-engineering notes: `docs/research/bdif-api-reverse-engineering.md`.

### New tech debt opened at phase 3

These items are explicitly **accepted** and scheduled — not blockers for paper trading on the current set of M&A notes.

| # | Item | Severity | Owner | Status |
|---|---|---|---|---|
| 1 | **Cleanup of leftover `AMF-SYN-*` rows in prod `ede` DB** (originally 13 rows from phase-2 live backfill before BDIF replaced the path) | low | Phase 4bis | **🟢 CLOSED 2026-05-14** (PR #4) — migration `0005_cleanup_amf_syn_legacy` shipped + run against live `ede`. Audit log in `artifacts/phase-04bis/cleanup-log.txt`. **Live finding**: the rows had already been removed by the `DROP DATABASE ede` reset before phase-3 backfill; the migration runs as a defensive no-op now and remains a safety net for any other env that still carries phase-2 data. Backup pre-cleanup: `artifacts/phase-04bis/backup-pre-cleanup-20260513T223650Z.sql` (120 KB). |
| 2 | **AMF document type expansion** — current BDIF ingestion only fetches `typesDocument=NotesEtAutresInformations` (1786 docs all-time). Targets to add: `DepotOffre` (997), `Decisions` (589), `CalendrierOffre` (885), `PreOffre` (328). Each enriches the timeline with follow-up events on existing deals (filing of supplementary documents, clearance decisions, opening/closing calendars, pre-offer rumours). | medium | **Phase 6 or 7 (under label "AMF document type expansion")** | 🟡 open — Same `BdifPoller` infra, only the `typesDocument` filter changes. Each type maps to a distinct `event_type` (already in `event_type_enum`). `PreOffre` bundled in this expansion — not split out as separate phase. |

### `Decimal` of accepted PR-questions from phase 3

> "Re-process the 13 phase-2 synthetic-ref rows in prod `ede` DB?" → **YES, in phase 4 or 4bis** (item #1 above).
>
> "Tighten or loosen the `OPA + NotesEtAutresInformations` filter?" → **Expand in phase 6-7** (item #2 above).
>
> "What about `PreOffre`?" → **Bundle with phase 6-7 expansion** (item #2 above).

---

## Consob (IT) — phase 4 ✅

### Endpoints

| Resource | URL pattern |
|---|---|
| Listing (HTML, paginated) | `https://www.consob.it/web/area-pubblica/documenti-opa?...&_it_consob_OpaDocumentsPortlet_delta=50&_it_consob_OpaDocumentsPortlet_cur={page}` |
| PDF (recent, ~2024+) | `https://www.consob.it/documents/11973/9797550/{filename}.pdf/{uuid}?...` |
| PDF (legacy archive) | `https://www.consob.it/documents/11973/543xxxx/{filename}.pdf/{uuid}?...` |

### Anti-bot landscape — Radware Bot Manager

The Consob site is fronted by Radware Bot Manager. Behavior observed in
Step-0 / Step-9 (2026-05-19):

| Endpoint family | Direct httpx | ScrapingBee (cheap config) |
|---|---|---|
| `/web/area-pubblica/documenti-opa` (listing) | **403 → validate.perfdrive.com captcha** | ✅ 1 credit/page, full HTML |
| `/documents/11973/9797550/*.pdf` (recent) | ✅ free, returns real PDF | (not needed) |
| `/documents/11973/543xxxx/*.pdf` (legacy) | **redirected to Radware captcha, returns 15 KB HTML** | ✅ 1 credit/PDF (fallback) |

The fetcher (`src/ingestion/consob/fetcher.py`) validates `%PDF-` magic bytes
on every response and falls back to ScrapingBee when direct httpx returns
non-PDF content.

### ScrapingBee config

- API base: `https://app.scrapingbee.com/api/v1/`
- **Auth: API key in `.env` (`SCRAPINGBEE_API_KEY`), NEVER committed.**
- Cheap config used (empirically validated cheapest viable on Consob):
  `render_js=false`, `premium_proxy=false` → **1 credit / call**
- Monthly budget: 900 of 1000-credit Free Tier (100 headroom for incremental
  ticks of the next month). Enforced via `vendor_api_usage` ledger
  (migration 0006). Discord alerts at 50/75/90% (phase 11).
- Step-9 backfill (12-month window, 22 deals, 22 PDFs): **2 credits consumed**.

### Logging hardening (Phase-4 Step-9 security fix)

- `httpx` and `httpcore` loggers are forced to `WARNING` in `src/core/logging.py`.
  Default INFO output included the full request URL with query string, which
  on the ScrapingBee endpoint contained `api_key=...`. Muting prevents repeat.
- **Operational rule (any new vendor integration): vendor API keys live in
  `.env`. NEVER log full URLs with query strings. Pass secrets via headers
  or POST body when the vendor supports it.**

### Italian deal-type classifier

`src/ingestion/consob/discovery.py::ITALIAN_TYPE_RULES` maps the narrative
description on each row to the canonical `DEAL_TYPES` enum:

| Italian narrative | Canonical |
|---|---|
| `acquisto e scambio`, `di scambio` | `opas` |
| `consolidamento` | `opa_consolidamento` |
| `residuale`, `obbligatoria` | `opa_obligatoire` |
| `volontaria totalitaria`, `volontaria preventiva`, `volontaria` | `opa_volontaire_totalitaria` |
| `volontaria parziale` | `opa_volontaire_parziale` |

### Dedup

- Unique key: `(juridiction='IT', regulator_ref)` where `regulator_ref =
  CONSOB-{pdf_filename_slug}` (e.g. `CONSOB-opa_bancasistema_20260511`).
- Fallback when no PDF link: `CONSOB-{slug(target)}-{slug(offerente)}-{YYYYMMDD}`.

### Polling cadence

- `run_backfill(since=today-365d)` — once at deploy, populates ~22 OPAs.
- `run_incremental(since=today-90d, stop_after_known=True)` — daily tick,
  breaks on first known `consob_ref`, typically 1 listing call + 0–2 PDFs.

### On-disk storage

```
data/pdfs/it/{year}/CONSOB-{slug}.pdf
```

Atomic write via `tempfile.mkstemp` + `os.replace`. Idempotent on rerun.

### Tech debt opened at phase 4

| # | Item | Severity | Owner |
|---|---|---|---|
| 1 | **4/22 deals carry `[pending parse]`** in `target_name` or `acquirer_name`. Discovery extractor is robust when both `<strong>` markers are present (offerente + target). Rows with missing markers leave the field unfilled. Resolution: the PDF body parser already extracts `target_name_from_pdf` / `offerente_name_from_pdf` — wire it to back-fill placeholders during upsert. | medium | phase 6 |
| 2 | **Consob *Comunicati ex art. 102 TUF*** (pre-OPA announcements, often days/weeks before the formal *documento d'offerta*) are not ingested. These are the earliest possible signal for an event-driven strategy. Resolution: add a sibling `ConsobComunicatiClient` in Phase 6-7 multi-document-type expansion (one extra listing endpoint, same Radware/ScrapingBee path). | medium | phase 6-7 |
| 3 | **Legacy archive PDFs (`/documents/11973/543xxxx/`)** require ScrapingBee fallback (~1 credit each) when ingested. Currently silently absorbed by the fallback path. Resolution: monitor the share of fallback hits via `vendor_api_usage.extra.fallback=true` and tune the budget if the historical-backfill scenario ever consumes >50 % of the monthly cap. | low | monitor |

### Phase-4 Step-9 incident — narrative-leak crash

The first 12-page run crashed on `StringDataRightTruncationError` after 252
rows. Two upstream causes (now fixed):

1. **Discovery extractor leaked the full narrative** into `target_name` /
   `acquirer_name` when `<strong>` tags were missing on a row (200+ char
   sentences overflowing the 255-char column). Fixed by `_trim_company_name`
   (cuts on first comma/period/narrative marker, caps at 120 chars) + a
   defensive 255-char truncation in `service._safe_name`.
2. **Direct httpx silently accepted 15 KB Radware captcha pages as "PDFs"**.
   Fixed by the `%PDF-` magic check + ScrapingBee fallback in `fetcher.py`.

## BaFin (DE) — phase 5 (pending)

## News & GDELT — phase 6 (pending)

## IBKR + Stooq prices — phase 6 (pending)

## DG COMP decisions — phase 6 (pending)
