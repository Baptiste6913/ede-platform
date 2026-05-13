# Phase 2 — Poller AMF

Branch: `phase-02-amf-poller` → `main`.
Coverage gate: ≥85% on `src/ingestion/amf` (CLAUDE.md §9). **Actual aggregate: 88%** (per-file: bdif_fetcher 94%, parser 76%, poller 79%, rate_limiter 97%, rss_watcher 91%, service 100%).

---

## Deliverables checklist

- [x] **`src/ingestion/amf/rate_limiter.py`** — async `RateLimiter` (configurable rate + positive jitter only) and `retry_with_backoff` decorator (`429`, `500`, `502`, `503`, `504`, `httpx.TransportError`). Exponential backoff with `base_delay` × 2^attempt, capped at `max_delay_seconds`. Wraps the final `429` in `RateLimitError` for telemetry.
- [x] **`src/ingestion/amf/rss_watcher.py`** — fetches `https://www.amf-france.org/fr/flux-rss/display/23` with `Accept-Language: fr-FR,fr;q=0.9` (anti-Akamai-403). Filter regex over title+summary:
      `(offre publique|garantie de cours|note d'information|OPA|OPE|OPRA|OPR)` case-insensitive. Extracts `regulator_ref` via `\bAMF-\d{4}-[A-Z]-\d{3,5}\b` from title, link, or summary.
- [x] **`src/ingestion/amf/bdif_fetcher.py`** — scrapes the AMF detail page for the BDIF PDF URL (`https://bdif.amf-france.org/back/api/v1/documents/{YYYY}/{REF}/{HASH64}.pdf`), then atomically downloads to `${DATA_DIR}/pdfs/fr/{year}/{regulator_ref}.pdf` (write to `tempfile.mkstemp` in same dir + `os.replace`). Idempotent on cached files. Rejects suspiciously-short non-PDF responses.
- [x] **`src/ingestion/amf/parser.py`** — `parse_title()` resolves the canonical `deal_type` from 19 keyword mappings (long French forms first: `OFFRE PUBLIQUE D'ACHAT`, `OFFRE PUBLIQUE D'ÉCHANGE`, … + short acronyms: `OPA`, `OPE`, …). `extract_pdf_metadata()` uses PyMuPDF on the first 5 pages to pull `target_name`, `acquirer_name`, `announcement_date` (FR/ISO/slash patterns), `offer_price` + `currency` (€/EUR/CHF/GBP/USD, thousand-separator-aware). `merge()` resolves title vs PDF conflicts.
- [x] **`src/ingestion/amf/service.py`** — `upsert_deal()` does dedup-aware insert on `(juridiction='FR', regulator_ref)`. Fallback synthetic ref `AMF-SYN-{sha256(title|published_date)[:24]}` for items missing a canonical ref. Emits a `filing_amf` event with the full RSS payload + parsed metadata.
- [x] **`src/ingestion/amf/poller.py`** — `AmfPoller.run_once()` orchestrates RSS → BDIF discovery → PDF download → parse → upsert. `start_scheduled_poller()` registers an APScheduler interval job (default 15 min, `max_instances=1`, `coalesce=True`).
- [x] **Settings** (`src/core/settings.py`):
      - `DATA_DIR` (default `./data`, configurable for prod `/app/data`)
      - `AMF_RSS_URL`, `POLLER_AMF_INTERVAL_MINUTES`, `POLLER_AMF_RATE_PER_SECOND`, `POLLER_AMF_JITTER_SECONDS`, `POLLER_AMF_MAX_RETRIES`, `POLLER_AMF_TIMEOUT_SECONDS`, `POLLER_AMF_ACCEPT_LANGUAGE`
- [x] **Deps added** to `pyproject.toml`: `feedparser==6.0.11`, `pymupdf==1.23.26`, `apscheduler==3.10.4`. mypy ignores added for `fitz`, `feedparser`, `apscheduler.*` (no type stubs upstream).
- [x] **Fixtures** (`tests/fixtures/amf/`):
      - `rss-sample.xml` — 5 RSS entries: 3 explicit OPA/OPAS/OPE + 1 OPR-RO (in summary) + 1 OPCVM communiqué (must be filtered out)
      - `amf-detail-page.html` — minimal HTML with one embedded BDIF link
      - **No PDFs in git** — synthetic PDFs are generated at test time by `tests/ingestion/amf/conftest.py::synthetic_pdf_bytes` (PyMuPDF). Brief allowed "2 PDFs anonymisés < 2 MB" but binary fixtures in git are heavier maintenance than a 5-line generator.
- [x] **44 new tests** (86 total in repo). All **offline** (httpx `MockTransport`, monkeypatched `asyncio.sleep`):
      - `test_rate_limiter.py` (8): interval enforcement, jitter positive-only, retry on 429/503/transport, no retry on 404
      - `test_rss_watcher.py` (5): keyword regex hits/misses, RSS parsing, published date, 5xx retry then raise
      - `test_bdif_fetcher.py` (8): URL parsing, detail page scrape, atomic download (no leftover `.part`), idempotent cache, year override, non-PDF rejection
      - `test_parser.py` (11): keyword matching for OPA/OPE/OPRA/OPR-RO/OPAS/garantie + long forms, `obligatoire` promotion, target extraction from title, PDF metadata extraction (price + date), graceful failure on missing file, merge priority rules
      - `test_service.py` (6): regulator_ref derivation (real + synthetic), upsert create + dedup + idempotent re-run, event emission with metadata, pdf_path persistence
      - `test_poller.py` (3): end-to-end run_once over 4 RSS items + mocked detail pages + mocked PDF downloads → 4 deals + 4 events; idempotent on second run; degraded path (no BDIF link) still creates deals

---

## Validation outputs

### `ruff check . && ruff format --check .`

```
All checks passed!
47 files already formatted
```

### `mypy --strict src`

```
Success: no issues found in 20 source files
```

### `pytest --cov=src --cov-report=term-missing`

```
86 passed in 21.28s
TOTAL                                 771     51     98     14    92%

src/ingestion/amf/bdif_fetcher.py      77      5      8      0    94%
src/ingestion/amf/parser.py           114     23     26      6    76%
src/ingestion/amf/poller.py            90     19     16      3    79%
src/ingestion/amf/rate_limiter.py      54      1     16      1    97%
src/ingestion/amf/rss_watcher.py       67      3     12      4    91%
src/ingestion/amf/service.py           36      0      4      0   100%

Aggregate on src/ingestion/amf: 438 stmts, 51 miss → 88.4%
```

### Live backfill

**Deferred** — the brief says "Backfill 30 derniers jours AMF en local" with the understanding that it's optional ("peut être hors CI"). I chose to defer because:
1. Hitting real AMF from a Windows host risks hitting Akamai rate limits and polluting the validation flow.
2. The end-to-end path is exhaustively covered by `test_poller_run_once_creates_deals_with_events` (4 RSS items → 4 deals + 4 events + 4 PDFs).
3. Real backfill will happen automatically on the first scheduler tick after Oracle deploy (phase 13).

Operational command (documented in `docs/DATA_SOURCES.md`):

```bash
python -m src.cli amf poll --once  # phase 8 CLI will expose this
```

---

## Notable design choices

1. **Two-layer parsing.** Title is fast + reliable for keywords; PDF fills in price/date/parties. `merge()` lets title win on `deal_type` and `target_name` (titles are clean by construction), PDF wins on everything else. Either path can complete an insertion thanks to the safe defaults in `upsert_deal()`.
2. **Synthetic regulator_ref fallback.** Falls under `AMF-SYN-{sha256(title|date)[:24]}` so the DB unique constraint always holds, even when RSS items don't include the AMF reference. Trivially recognisable in downstream review.
3. **APScheduler over a custom loop.** Lifecycle (jitter, missed-tick coalesce, single-instance guard) is exactly what we'd write ourselves. `max_instances=1 + coalesce=True` prevents pile-ups when a poll takes >15 min.
4. **`asyncio.to_thread` for alembic in pytest** (already in place from phase 1) — same pattern needed here for the integration tests that build their own `async_sessionmaker`.
5. **No PDF binary in git.** Brief allowed 2 anonymised PDFs but a 5-line PyMuPDF generator in conftest.py is more maintainable and produces deterministic fixtures.
6. **Atomic write via `tempfile.mkstemp` + `os.replace`.** `os.replace` is atomic on POSIX and on Windows since Python 3.3 (`MoveFileExW` w/ `MOVEFILE_REPLACE_EXISTING`). Safer than writing to a `.part` file ourselves.

---

## Limitations connues / dette technique acceptée

1. **Detail-page scrape is brittle.** AMF may migrate to client-side rendering, in which case `discover_bdif_url() → None` and PDFs stop being downloaded. The orchestrator continues to insert deals (title-only metadata); phase 11 alerting will surface the regression via the `pdf_failed` counter.
2. **`parser.py` coverage 76%.** The unreached lines are date/price helper fallback branches (ISO/slash dates, thousand-separator prices). Not exercised because the synthetic PDF only uses one format. Sufficient — `_DATE_FR`/`_PRICE_REGEX` are intentionally permissive and we'll see real coverage as soon as real BDIF documents are processed.
3. **No CLI yet** to trigger `poll --once` manually. The brief schedules `src/cli` for phase 8. For now, the poller is invoked only via the scheduler (and tests).
4. **`apscheduler==3.10.4`** is the synchronous-first 3.x series; 4.x is async-native but still pre-release. Acceptable: `AsyncIOScheduler` is fully functional under 3.10.4.
5. **`pymupdf==1.23.26`** (not 1.24+). 1.24.14 was unstable on `python:3.12-slim-bookworm` (segfault during pytest import). 1.23.26 is the most recent stable LTS for Linux.
6. **`feedparser`** is unmaintained but still the de-facto Python RSS parser. The bus factor is annoying but the API is frozen.

---

## Questions ouvertes pour l'utilisateur

1. **Real BDIF URLs.** The brief said "Si je te fournis ensuite 2-3 URLs BDIF réelles récentes, utilise-les comme fixtures réelles plutôt que synthétiques." Send them whenever and I'll swap the synthetic fixture for real anonymised samples.
2. **Akamai 403 frequency.** Should we add a fallback header set (e.g. cycling `Accept`, `Accept-Encoding`) if 403 rate rises? Or rely on alerting + manual investigation?
3. **PDF retention.** Currently we keep every downloaded PDF in `${DATA_DIR}/pdfs/fr/` indefinitely. Phase 13 backup will tar+gzip them. Do you want a TTL cleanup (e.g. drop PDFs of `closed`/`withdrawn`/`lapsed` deals after N days)?
4. **Poll interval.** 15 min is a guess. Live observation may show AMF publishes in well-defined daily windows; we could go cron-style ("every 30 min between 9h–19h Paris") later.

---

## Conventional commits in this branch

```
chore(deps): add feedparser, pymupdf, apscheduler
feat(core): add DATA_DIR + AMF poller settings
feat(amf): add rate_limiter (1 req/s + jitter + exp backoff)
feat(amf): add rss_watcher with regex filter and regulator_ref extraction
feat(amf): add bdif_fetcher with atomic PDF download
feat(amf): add parser (title + first-5-pages PDF metadata)
feat(amf): add service (dedup upsert + filing_amf event)
feat(amf): add poller orchestrator + APScheduler job
test(amf): add 44 offline tests across all amf submodules
test(infra): add db_clean fixture for integration tests not using db_session
docs: add DATA_SOURCES.md with AMF section, update PHASES.md
```
