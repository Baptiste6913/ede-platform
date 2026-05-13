# Data sources — provenance, rate limits, storage layout

Each ingestion module documents here:
- the upstream URL(s) and protocol
- the rate-limit policy applied client-side
- the User-Agent we send
- the dedup strategy
- the on-disk storage layout for any downloaded artifacts
- the operational caveats (latency, holidays, redesigns, etc.)

---

## AMF — Autorité des Marchés Financiers (FR) — phase 2 ✅

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
python -m src.cli amf poll --once

# Inspect storage
ls data/pdfs/fr/2025/
```

---

## Consob (IT) — phase 3 (pending)

## BaFin (DE) — phase 4 (pending)

## News & GDELT — phase 5 (pending)

## IBKR + Stooq prices — phase 5 (pending)

## DG COMP decisions — phase 5 (pending)
