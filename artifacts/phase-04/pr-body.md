## Summary

Phase 4 — **Consob (IT) M&A poller** ships authoritative ingestion of the *documenti d'offerta* listing, with Radware bypass via ScrapingBee, atomic PDF download (free for recent docs, paid fallback for legacy archive), Italian PDF metadata extraction, and a generic `vendor_api_usage` ledger that enforces a 900-credit/month budget cap (1000-credit Free Tier with 100-credit headroom).

Live Step-9 backfill: **22 OPAs ingested + 22 PDFs (12-month window) for 2 ScrapingBee credits, AMF FR=60 baseline unchanged, 151 tests passing, 91 % coverage.**

## Success criteria

| # | Criterion | Target | Actual |
|---|---|---|---|
| 1 | OPAs IT discovered (12-month window) | ≥10 | **22** |
| 2 | PDFs downloaded + parsed validated (%PDF- magic) | ≥5 | **22** (0 failed) |
| 3 | Known-deal manual validation | ≥1 of 3 | **MPS→Mediobanca** id 342 ✓ |
| 4 | ScrapingBee credits consumed | ≤30 | **2** (898/900 remaining) |
| 5 | AMF no regression (FR=60, filing_amf=60) | unchanged | **FR=60, 60 events** |
| 6 | CI green, coverage ≥80 % | green | **151 passed, 91 %** |

Banco BPM/Anima (2025-03-17, 428 d ago) and UniCredit/BPM (2025-04-28, 386 d ago) fall just outside the 365-day window. They were correctly captured in the earlier debug run that walked back to 2010 — the extractor works for them; they're simply not within the operational window.

## Step-9 live findings — first run crashed, then fixed

The initial 12-page run (`scripts/consob_run_once.py 12`) crashed on `StringDataRightTruncationError` after 252 rows and exposed three Step-0 false-positives. **4 patches landed; the re-run was a clean success.**

### Patch 1 — `fetcher.py` : PDFs `/documents/11973/543xxxx/` (legacy) ARE Radware-protected

Step-0 tested a single PDF URL family that happened to slip through. The legacy archive (`/543xxxx/`) returns a 15 KB Radware captcha HTML page disguised at the `.pdf` URL — the content-length check (`len < 1024`) didn't trigger because the captcha page is bigger than the threshold.

**Fix:** validate `%PDF-` magic bytes on every download; fall back to ScrapingBee (~1 credit/PDF) when direct httpx returns non-PDF content. Recent PDFs (`/9797550/`) continue to download for free.

### Patch 2 — `discovery.py` + `service.py` : `acquirer_name` leak

When a row's `<strong>` markers were missing, the extractor's regex fallback captured the full offer narrative (200+ chars) into `acquirer_name`, overflowing the 255-char column.

**Fix:**
- `_trim_company_name` cuts on first `,`/`.`/`;`/`:`/`(` or narrative marker (`ai sensi`, `avente`, `rappresentative`, `ad un`, `al prezzo`) and hard-caps at 120 chars.
- Defensive 255-char truncation in `service._safe_name` — belt-and-suspenders against future extractor leaks.

### Patch 3 — `poller.py` : `max_pages=12` walked 16 years, not 12 months

`max_pages=12 × 50 rows/page ≈ 600 rows` and Consob has ~40 OPAs/year, so the script walked back to **2010-2011** instead of the intended 12-month window.

**Fix:**
- `iter_all(since: date | None)` stops pagination as soon as every row on a page is older than the floor.
- `run_backfill(since=today-365d)` and `run_incremental(since=today-90d)` defaults.

### Patch 4 — HTML rows without `<strong>` markers → `[pending parse]`

4 of the 22 deals still carry `[pending parse]` in `target_name` or `acquirer_name`. Discovery is robust when both `<strong>` markers exist; rows missing them leave the field unfilled rather than crash. **Tech debt opened, owner phase 6**: the PDF body parser already extracts `target_name_from_pdf` / `offerente_name_from_pdf` — wire it to back-fill placeholders during upsert.

## 🔒 Security — ScrapingBee key was logged

During the failed first run, `httpx`'s INFO-level handler emitted the full request URL (with `?api_key=…` query string) to stdout. The leak landed in `artifacts/phase-04/consob-backfill-stdout.txt`.

**Mitigations applied immediately:**
1. **Artifact scrubbed** (`api_key=…` → `api_key=[REDACTED]`); `grep -r 'api_key=[A-Za-z0-9]{30,}'` on the entire repo returns 0 hits.
2. **`src/core/logging.py` hardened** — `httpx` and `httpcore` loggers forced to `WARNING`. Service-layer structlog calls carry `target_url`, `status`, `cost` but no raw URL with credentials.
3. Clean re-run confirms no `api_key=` string is emitted any more.
4. **Operator rotated the ScrapingBee key 3 ×** during the phase (most recent rotation: post-leak, post-hardening).

Operational rule now documented in `docs/DATA_SOURCES.md`:
> Vendor API keys live in `.env`. NEVER log full URLs with query strings. Pass secrets via headers or POST body when the vendor supports it.

## ScrapingBee budget

| Item | Value |
|---|---|
| Free Tier | 1000 credits/month |
| Configured monthly cap | 900 (100 headroom for incremental ticks of next month) |
| Step-9 12-month backfill | **2 credits** (1 listing page × 2 pages = 2 calls) |
| Daily incremental cost (estimate) | 1 listing page + 0–2 PDFs ≈ 1–3 credits/day |
| Monthly cost (estimate, ongoing) | ≈ 30–90 credits/month |
| Annual budget for backfill of historical archive | ≈ 250–300 credits one-time (legacy PDFs via fallback) |

## Tech debt opened at phase 4 (documented in `docs/DATA_SOURCES.md`)

| # | Item | Severity | Owner |
|---|---|---|---|
| 1 | 4/22 deals carry `[pending parse]` (HTML rows without `<strong>` markers) | medium | phase 6 |
| 2 | Consob *Comunicati ex art. 102 TUF* (pre-OPA announcements) not ingested | medium | phase 6-7 |
| 3 | Legacy archive PDFs `/543xxxx/` consume ScrapingBee fallback (~1 credit each) | low | monitor |

## Files changed

```
alembic/versions/20260519_1000_0006_vendor_api_usage.py   (new)
src/core/models.py                                        (+ VendorApiUsage)
src/core/settings.py                                      (+ scrapingbee_*)
src/core/logging.py                                       (+ httpx/httpcore WARNING mute)
src/ingestion/consob/__init__.py                          (new)
src/ingestion/consob/scrapingbee_client.py                (new)
src/ingestion/consob/discovery.py                         (new + Step-9 patches)
src/ingestion/consob/fetcher.py                           (new + %PDF- + SB fallback)
src/ingestion/consob/parser.py                            (new)
src/ingestion/consob/service.py                           (new + _safe_name)
src/ingestion/consob/poller.py                            (new + since= defaults)
scripts/consob_run_once.py                                (new)
scripts/scrapingbee_test.py                               (new)
tests/conftest.py                                         (+ vendor_api_usage truncate)
tests/fixtures/consob/documenti-opa-page1.html            (new, 85 KB capture)
tests/ingestion/consob/test_discovery.py                  (new + 4 new tests)
tests/ingestion/consob/test_scrapingbee_client.py         (new)
tests/ingestion/consob/test_parser.py                     (new)
tests/ingestion/consob/test_service.py                    (new + truncation test)
tests/ingestion/consob/test_poller.py                     (new + since=2010-01-01)
tests/ingestion/consob/test_fetcher.py                    (new, 3 tests for fixes)
docs/DATA_SOURCES.md                                      (+ Consob section + tech debt)
docs/PHASES.md                                            (Phase 4 status → done)
pyproject.toml                                            (+ bs4, lxml, filterwarnings)
artifacts/phase-04/{consob-backfill.json,consob-backfill-audit.md,consob-backfill-stdout.txt,pr-body.md}
```

## Test plan

- [ ] CI green: lint (ruff) + mypy + 151 pytest + coverage ≥80 % (currently 91 %)
- [ ] Reviewer can replay backfill: `python scripts/consob_run_once.py 12` with `SCRAPINGBEE_API_KEY` in `.env` → produces `artifacts/phase-04/consob-backfill.json` with `discovered=created=pdf_downloaded=22`, `credits_consumed_run=2`
- [ ] Reviewer can verify AMF baseline: `SELECT COUNT(*) FROM deals WHERE juridiction='FR';` returns 60, `SELECT COUNT(*) FROM events WHERE event_type='filing_amf';` returns 60
- [ ] Reviewer can verify no key leakage: `grep -r 'api_key=[A-Za-z0-9]\{30,\}' .` returns 0 hits

🤖 Generated with [Claude Code](https://claude.com/claude-code)
