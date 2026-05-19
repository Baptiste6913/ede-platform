# Phase 4 — Step 9 Consob Live Backfill Audit

**Date:** 2026-05-19
**Branch:** `phase-04-consob` (not yet PR'd — awaiting user VALIDATE)
**Script:** `python scripts/consob_run_once.py 12`
**ScrapingBee key:** rotated 2026-05-19, loaded from `.env` (gitignored)

---

## TL;DR

| Criterion | Target | Actual | Pass |
|---|---|---|---|
| OPAs IT discovered (12-month window) | ≥10 | **22** | ✅ |
| PDFs downloaded & validated | ≥5 | **22** (0 failed) | ✅ |
| Known-deal validation | ≥1 of 3 | **1/3** (MPS→Mediobanca) | ✅ |
| ScrapingBee credits consumed | ≤30 | **2** | ✅ |
| AMF regression | FR=60 unchanged | FR=60 + 60 filing_amf events | ✅ |
| CI / coverage | green ≥80% | **151 passed, 91% coverage** | ✅ |

---

## Run summary (artifact: `consob-backfill.json`)

```
discovered:        22
created:           22  (0 skipped, 0 duplicates)
pdf_downloaded:    22  (0 failed)
credits consumed:   2  (898 remaining of 900-credit cap)
duration:        40.8 s
stop reason:    `consob.discovery.stop_on_since` page 2 — every row older than 2025-05-19
```

## DB state (after re-run)

```
juridiction | deals | filing events
FR          |    60 | 60 (filing_amf)   — baseline preserved
IT          |    22 | 22 (filing_consob)
```

## IT deals (newest first)

| # | regulator_ref | target | acquirer | type | date | PDF |
|---|---|---|---|---|---|---|
| 326 | opa_bancasistema_20260511 | Banca Sistema Spa | Banca CF+ Credito Fondiario Spa | opas | 2026-05-11 | ✓ |
| 327 | opa_cir_20260427 | `[pending parse]` | Cir Spa | volontaria parziale | 2026-04-27 | ✓ |
| 328 | opa_danzic_20260424 | Digital Value Spa | Oep Danzig BidCo Spa | obbligatoria | 2026-04-24 | ✓ |
| 329 | opa_nextre_20260420 | Next Re SIIQ Spa | CPI Property Group Sa | volontaria totalitaria | 2026-04-20 | ✓ |
| 330 | opa_banco_desio_20260330 | Solutions Capital Management Sim Spa | Banco di Desio e della Brianza Spa | volontaria totalitaria | 2026-03-30 | ✓ |
| 331 | opa_ferretti_20260316 | Ferretti Spa | Azúr as | volontaria parziale | 2026-03-16 | ✓ |
| 332 | opa_Tinexta_20260223 | Tinexta Spa | `[pending parse]` | obbligatoria | 2026-02-23 | ✓ |
| 333 | opa_antares_20260216 | `[pending parse]` | `[pending parse]` | obbligatoria | 2026-02-16 | ✓ |
| 334 | opa_health_italia_20260409 | Health Italia Spa | Lonvita Spa | obbligatoria | 2026-02-09 | ✓ |
| 335 | opas_Banca_Sistema_20260116 | Banca Sistema Spa | Banca CF+ Credito Fondiario Spa | opas | 2026-01-16 | ✓ |
| 336 | opa_eles_20260105 | Eles Semiconductor Equipment Spa | Ebidco srl | obbligatoria | 2026-01-05 | ✓ |
| 337 | opa_spindox_20251215 | Spindox Spa | BackSpin Spa | obbligatoria | 2025-12-15 | ✓ |
| 338 | opa_mare_20251205 | Eles Semiconductor Equipment Spa | Mare Engineering Group Spa | volontaria totalitaria | 2025-12-05 | ✓ |
| 339 | opa_ala_20251201 | Ala Spa | Wing BidCo Spa | obbligatoria | 2025-12-01 | ✓ |
| 340 | opa_almawave_20251117 | Almawave Spa | Almaviva Spa | volontaria totalitaria | 2025-11-17 | ✓ |
| 341 | opa_palingeo_20251027 | Palingeo | Icop Spa Società Benefit | obbligatoria | 2025-10-27 | ✓ |
| **342** | **ops_montepaschi_20250714** | **Mediobanca-Banca di Credito Finanziario Spa** | **Banca Monte dei Paschi di Siena Spa** | **opas** | **2025-07-14** | **✓ (known deal #1)** |
| 343 | opa_bialetti_20250707 | Bialetti Spa | Octagon BidCo Spa | obbligatoria | 2025-07-07 | ✓ |
| 344 | ops_Banca_Popolare_Sondrio_20250616 | Banca Popolare di Sondrio S | `[pending parse]` | opas | 2025-06-16 | ✓ |
| 345 | opa_Alkemy_20250609 | Alkemy S | `[pending parse]` | volontaria totalitaria | 2025-06-09 | ✓ |
| 346 | Opa_IlSole24Ore_20250603 | Il Sole 24 Ore Spa | Zenit Spa | volontaria totalitaria | 2025-06-03 | ✓ |
| 347 | opa_illimity_20250519 | Illimity Bank Spa | Banca Ifis Spa | opas | 2025-05-19 | ✓ |

## Known-deal validation

| Deal | Expected | Status |
|---|---|---|
| **MPS → Mediobanca** (`ops_montepaschi_20250714`) | offerente=MPS, target=Mediobanca, opas | ✅ id 342 — fields correct |
| **UniCredit → Banco BPM** | 2025-04-28 | ❌ outside 365-day window (filed 386 days ago) |
| **Banco BPM → Anima Holding** | 2025-03-17 | ❌ outside 365-day window (filed 428 days ago) |

The 12-month cutoff (since=2025-05-19) excludes the two earlier deals. Both were correctly captured in the prior debug run that walked back to 2010 — extractor works for them, they simply fall outside the operational window. Widening to `since=2025-01-01` would pick them up at a cost of ~1 extra ScrapingBee credit if needed for re-validation.

---

## What changed between the first failed run and this successful one

The first 12-page run discovered 252 historical rows then crashed on row 252
(`StringDataRightTruncationError` — narrative leaked into `acquirer_name`). Root
causes:

1. **PDFs at `/documents/11973/543xxxx/`** (legacy archive) ARE Radware-protected.
   The fetcher's direct httpx received 15 KB Radware HTML captcha pages but kept
   the bytes because the content-length check (`len < 1024`) didn't trigger. The
   bytes weren't real PDFs.
2. **Discovery extractor** sometimes captured the entire offer narrative into
   `target_name` / `acquirer_name` when `<strong>` tags were missing — overflowing
   the 255-char column.
3. **`max_pages=12` walks 12 listing pages of 50 rows = 16 years of history**,
   not 12 months.

### Fixes (4 patches, no migration needed)

| # | File | Change |
|---|---|---|
| A | `src/ingestion/consob/discovery.py` | `_trim_company_name` cuts on first comma/period/narrative marker, hard-caps at 120 chars. `iter_all` accepts `since: date \| None` and stops pagination when every row on a page is older. |
| B | `src/ingestion/consob/fetcher.py` | Validates downloaded body starts with `%PDF-` magic; falls back to ScrapingBee (1 credit/PDF) when direct httpx returns non-PDF. |
| C | `src/ingestion/consob/service.py` | Defensive 255-char truncation on `target_name` / `acquirer_name` — belt-and-suspenders against any future extractor leak. |
| D | `src/ingestion/consob/poller.py` | `run_backfill` defaults to `since=today-365d`; `run_incremental` to `since=today-90d`. Wires ScrapingBee into the PDF fetcher. |

### Test additions (+5)

- `test_trim_company_name_cuts_on_first_comma_marker` (Tinexta case)
- `test_trim_company_name_cuts_on_rappresentative_marker` (Almawave case)
- `test_trim_company_name_caps_at_120_chars`
- `test_upsert_truncates_overlong_names_to_255_chars`
- `test_iter_all_stops_when_all_rows_older_than_since`
- `tests/ingestion/consob/test_fetcher.py` (new file, 3 tests for PDF-magic + ScrapingBee fallback)

---

## ⚠️ Security finding — ScrapingBee key was logged

During the first failed run, `httpx`'s INFO-level handler emitted the full
request URL — including `?api_key=…` — to stdout. The leaked output landed in
`artifacts/phase-04/consob-backfill-stdout.txt`.

### Mitigations applied immediately

1. **Artifact scrubbed:** `consob-backfill-stdout.txt` rewritten with
   `api_key=[REDACTED]`. Grep across the whole repo for `api_key=[A-Za-z0-9]{30,}`
   returns 0 hits.
2. **Logging permanently muted:** `src/core/logging.py` now sets `httpx` and
   `httpcore` loggers to `WARNING`. Our structlog calls (service-layer) carry
   `target_url`, `status`, `cost` but never the request URL with credentials.
3. **Clean re-run** confirms no `api_key=` string is emitted any more.

### Residual exposure & recommendation

- The leaked key may still be present in your terminal scrollback and in the
  tool-result history of this Claude conversation.
- **Please rotate the ScrapingBee key once more** at
  `https://app.scrapingbee.com/dashboard` and update `.env` line 49. The newly
  hardened logging won't leak it again.

---

## Tech debt opened by this phase

1. **4 of 22 deals** still have `[pending parse]` in `target_name` or
   `acquirer_name` (rows 327 cir, 332 Tinexta acquirer, 333 antares both,
   344 BancaPopSondrio acquirer, 345 Alkemy acquirer). Discovery extractor
   handles strong-tagged rows perfectly but struggles when both `<strong>`
   markers are missing. **Resolution path:** Phase 6-7 PDF-body parser will
   back-fill these from the documento d'offerta itself (text-extraction-based).
2. **Consob Comunicati art. 102** (pre-OPA announcements, often days/weeks
   before the formal documento d'offerta) are **not ingested** in phase 4.
   Bundle in Phase 6-7 multi-jurisdiction document-type expansion.
3. **Legacy archive PDFs (`/documents/11973/543xxxx/`)** require ScrapingBee
   fallback (already wired). Recent PDFs (`/documents/11973/9797550/`) download
   free via direct httpx. No action needed.

---

## Files written / changed this round

```
src/core/logging.py                           (+8 lines, httpx mute)
src/ingestion/consob/discovery.py             (name-trim + since cutoff)
src/ingestion/consob/fetcher.py               (%PDF- magic + SB fallback)
src/ingestion/consob/service.py               (_safe_name truncation)
src/ingestion/consob/poller.py                (since default + SB wiring)
tests/ingestion/consob/test_discovery.py      (+4 tests)
tests/ingestion/consob/test_service.py        (+1 test)
tests/ingestion/consob/test_poller.py         (since=2010-01-01 in fixtures)
tests/ingestion/consob/test_fetcher.py        (NEW, 3 tests)
artifacts/phase-04/consob-backfill.json       (success payload)
artifacts/phase-04/consob-backfill-stdout.txt (scrubbed)
artifacts/phase-04/consob-backfill-audit.md   (this file)
```

---

**Next:** awaiting user VALIDATE before opening PR. Per Phase-4 brief:
> 8. STOP avant ouverture PR — attends mon VALIDATE final
