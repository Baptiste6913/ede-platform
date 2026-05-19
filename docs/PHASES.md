# Phases — status & validation journal

> Phase progression is **strictly sequential**. Phase N+1 cannot start without `VALIDATE PHASE N` from the user. See `CLAUDE.md` §6.

| # | Phase | Status | Branch | PR | Validated |
|---|---|---|---|---|---|
| 0 | Bootstrap repo & Oracle setup | 🟢 done | `phase-00-bootstrap` | merged ff-only into main | 2026-05-12 |
| 1 | Schema DB & migrations | 🟢 done | `phase-01-schema` | [#1 merged](https://github.com/Baptiste6913/ede-platform/pull/1) | 2026-05-12 |
| 2 | Poller AMF (RSS) | 🟢 done | `phase-02-amf-poller` | [#2 merged](https://github.com/Baptiste6913/ede-platform/pull/2) | 2026-05-13 |
| 3 | AMF BDIF scraper + close phase 2 tech debt | 🟢 done | `phase-03-amf-bdif` | [#3 merged](https://github.com/Baptiste6913/ede-platform/pull/3) | 2026-05-13 |
| 4bis | Cleanup `AMF-SYN-*` legacy rows | 🟡 in_progress | `phase-04bis-cleanup-amf-syn` | — | — |
| 4 | Poller Consob | ⚪ pending | — | — | — |
| 5 | Poller BaFin | ⚪ pending | — | — | — |
| 6 | News & marché data | ⚪ pending | — | — | — |
| 7 | Enrichment / PDF parsing & NLP | ⚪ pending | — | — | — |
| 8 | Scoring engine v0 | ⚪ pending | — | — | — |
| 9 | Module Analyst (Claude Code SDK) | ⚪ pending | — | — | — |
| 10 | API FastAPI | ⚪ pending | — | — | — |
| 11 | Streamlit dashboard MVP | ⚪ pending | — | — | — |
| 12 | Alerting Discord | ⚪ pending | — | — | — |
| 13 | Paper trading engine + backtest | ⚪ pending | — | — | — |
| 14 | Deploy Oracle production + monitoring | ⚪ pending | — | — | — |

Legend: 🟢 done · 🟡 in_progress · 🔴 blocked · ⚪ pending

---

## Phase 0 — Bootstrap repo & Oracle setup

### Deliverables checklist

- [x] `scripts/oracle_bootstrap.sh` (Ampere ARM provisioning, ufw, fail2ban, unattended upgrades, keep-alive cron install)
- [x] `Dockerfile` multi-stage (`python:3.12-slim-bookworm`, non-root user, tini, healthcheck)
- [x] `docker-compose.yml` (postgres `timescale/timescaledb-ha:pg16`, redis, app)
- [x] `pyproject.toml` (deps minimales + ruff/mypy/pytest config)
- [x] `src/core/settings.py` (pydantic-settings v2, SecretStr, lru_cache)
- [x] `src/core/logging.py` (structlog JSON + correlation_id contextvar)
- [x] `src/core/db.py` (async engine, sessionmaker, `ping()`, `dispose_engine()`)
- [x] `src/core/exceptions.py` (typed hierarchy: EDEError, ConfigurationError, DatabaseError, ExternalServiceError, RateLimitError, NotFoundError)
- [x] `src/api/main.py` (FastAPI factory + lifespan)
- [x] `src/api/middleware.py` (CorrelationIdMiddleware)
- [x] `src/api/routes_health.py` (`GET /health` → `{status, version, uptime_seconds, db}`)
- [x] `scripts/healthcheck_keep_alive.sh` (5min CPU activity, every 6h via cron)
- [x] `scripts/backup_nightly.sh` (stub; full impl phase 13)
- [x] `.github/workflows/ci.yml` (matrix: lint + test, pip cache)
- [x] `.pre-commit-config.yaml` (ruff + ruff-format + mypy --strict)
- [x] `README.md` (Local dev + Oracle deploy)
- [x] `docs/ARCHITECTURE.md` v0 (diagramme ASCII)
- [x] `docs/PHASES.md` (cette table)

### Test artifacts

- See `artifacts/phase-00/PR.md` for the full PR body (pytest --cov, ruff, mypy, docker compose ps outputs).

### Known limitations / open questions

- Recorded in `artifacts/phase-00/PR.md` under "Limitations connues / questions ouvertes".

### Validation

✅ `VALIDATE PHASE 0` received 2026-05-12. Merged ff-only into `main` at SHA `8353216`.

---

## Phase 1 — Schema DB & migrations

### Deliverables checklist

- [x] `alembic.ini` + `alembic/env.py` (async, reads `DATABASE_URL` from settings, `compare_type=True`)
- [x] `src/core/enums.py` — 11 Literal aliases + value tuples (single source of truth)
- [x] `src/core/models.py` — 6 ORM models (`Deal`, `Event`, `Score`, `Analysis`, `PaperPosition`, `Price`) with `Mapped`/`mapped_column`
- [x] Migration `0001` — Postgres ENUM types (jurisdiction, deal_type, deal_status, event_type, decision, analyst_verdict, analyst_source, position_side, position_status, currency, price_source)
- [x] Migration `0002` — `deals` + `events` + `scores` + `analyses` + `paper_positions` with FK `deal_id` ON DELETE CASCADE, composite indexes, check constraints
- [x] Migration `0003` — `prices` table, `create_hypertable` via TimescaleDB raw SQL, 1h and 1d continuous aggregates with refresh policies
- [x] `tests/fixtures/seed_deals.py` — 10 deals: 3 FR (OPA, OPAS, OPE) + 3 IT (OPV, OPVS, OPA_IT) + 4 DE incl. cross-border (Uebernahmeangebot, Pflichtangebot, Erwerbsangebot, dual-listed)
- [x] `tests/core/test_models.py` — 20 CRUD/constraint tests (≥3 per table), incl. 4× cascade-delete and 1× unique-constraint and 1× check-constraint and 1× hypertable-presence and 1× continuous-aggregates-presence
- [x] CI updated — `timescale/timescaledb-ha:pg16` service, `TEST_DATABASE_URL`, reversibility step (`alembic upgrade head` → `downgrade base` → `upgrade head`)

### Validation outputs

- `ruff check . && ruff format --check .` → clean
- `mypy --strict src` → 12 source files, no issues
- `alembic upgrade head → downgrade base → upgrade head` → reversible, 6 migration operations OK
- `pytest --cov=src` → **42 passed**, coverage **100%** (322 statements / 16 branches)
- `docker compose exec postgres psql -c "\dt"` → 7 tables (6 + alembic_version) — see `artifacts/phase-01/psql-dt.txt`
- TimescaleDB info — see `artifacts/phase-01/psql-hypertables.txt` (1 hypertable: prices) + `psql-continuous-aggregates.txt` (prices_1h, prices_1d)
- 11 Postgres ENUM types — see `artifacts/phase-01/psql-enums.txt`

### Known limitations / open questions

- Recorded in `artifacts/phase-01/pr-body.md` under "Limitations connues / questions ouvertes".

### Validation

✅ `VALIDATE PHASE 1` received 2026-05-12. Three post-validation actions completed:

1. Migration `0004_secondary_jurisdictions_and_deal_type_canonical` adds `deals.secondary_jurisdictions jurisdiction_enum[]` and replaces the placeholder `deal_type_enum` (12 v1 values) with the canonical 16-value lowercase legal-terminology list; `prices.volume` re-confirmed nullable. Reversible against TimescaleDB pg16.
2. Test self-review (AST-based): **44 tests, 0 cosmetic** — every test has at least one behavioural assertion. Audit in `artifacts/phase-01/tests-audit-output.txt`.
3. PR [#1](https://github.com/Baptiste6913/ede-platform/pull/1) opened via `gh pr create`, CI green (lint + tests), merged via `gh pr merge --merge --delete-branch` at SHA `0ad7902` on `main`.

---

## Phase 2 — Poller AMF

### Deliverables checklist

- [x] `src/ingestion/amf/rate_limiter.py` — async RateLimiter (1 req/s + jitter) + `retry_with_backoff` (429/5xx + transport errors)
- [x] `src/ingestion/amf/rss_watcher.py` — fetch AMF RSS + regex filter (`offre publique|garantie de cours|note d'information|OPA|OPE|OPRA|OPR`) + regulator_ref extraction
- [x] `src/ingestion/amf/bdif_fetcher.py` — scrape detail page for BDIF URL + atomic download (`tempfile.mkstemp` + `os.replace`) to `${DATA_DIR}/pdfs/fr/{year}/{ref}.pdf`
- [x] `src/ingestion/amf/parser.py` — `parse_title()` + `extract_pdf_metadata()` (PyMuPDF, first 5 pages); 16 deal_type keyword mappings (long French forms + short acronyms)
- [x] `src/ingestion/amf/service.py` — dedup on `(juridiction='FR', regulator_ref)` with `AMF-SYN-{sha256[:24]}` fallback; emits `filing_amf` event
- [x] `src/ingestion/amf/poller.py` — `AmfPoller.run_once()` orchestrator + `start_scheduled_poller()` (APScheduler 15 min interval, configurable, `max_instances=1`, `coalesce=True`)
- [x] Settings additions: `DATA_DIR`, `AMF_RSS_URL`, `POLLER_AMF_*` knobs (interval, rate, jitter, retries, timeout, accept-language)
- [x] Fixtures: `tests/fixtures/amf/rss-sample.xml` (5 entries, 4 matching), `tests/fixtures/amf/amf-detail-page.html`, on-the-fly synthetic PDF generator (PyMuPDF)
- [x] **44 new tests** (8 bdif, 11 parser, 8 rate_limiter, 5 rss_watcher, 6 service, 3 poller, 3 cleanup) — all offline (httpx MockTransport), zero network in CI

### Validation outputs

- `ruff check . && ruff format --check .` → clean
- `mypy --strict src` → 20 source files, no issues
- `pytest --cov=src` → **86 passed**, coverage **92%** total / **88% aggregate** on `src/ingestion/amf`
  - bdif_fetcher 94%, parser 76%, poller 79%, rate_limiter 97%, rss_watcher 91%, service 100%
- Live backfill **deferred** — code path verified end-to-end against fixture transport; real AMF backfill will run on the Oracle deploy (phase 13). Documented procedure in `docs/DATA_SOURCES.md`.

### Known limitations / open questions

- Recorded in `artifacts/phase-02/pr-body.md` under "Limitations connues / questions ouvertes".
- **Live backfill 2026-05-13** confirmed the pipeline end-to-end (RSS 200 OK, regex filter, dedup, DB insert, event emission) but flagged a configuration gap: `display/23` is the AMF "Communiqués" feed, not the BDIF filings feed → 0 PDFs downloaded. Tracked as **medium-severity technical debt** in `docs/DATA_SOURCES.md` under "Known gaps", **owner phase 3 ingestion enhancement**. Does not block paper trading on manually-tracked deals.

### Validation

✅ `VALIDATE PHASE 2` received 2026-05-13. Live backfill ran on real AMF feed (200 items → 13 matches → 13 deals + 13 `filing_amf` events inserted) with **zero Akamai 403** (`Accept-Language: fr-FR,fr;q=0.9` header validated). The BDIF document discovery gap (display/23 ≠ BDIF feed) is recorded as deferred tech debt and accepted as not-blocking.

---

## Phase 3 — AMF BDIF scraper + close phase-2 tech debt

### Deliverables checklist

- [x] **Reverse-engineer the BDIF API** — `docs/research/bdif-api-reverse-engineering.md` documents the public `GET /back/api/v1/informations` endpoint (no auth required, pagination via `From`/`Size`, filterable via `typesInformation`/`typesDocument`/`typesOperation`) and the `GET /back/api/v1/documents/{path}` PDF endpoint.
- [x] **`src/ingestion/amf/bdif_api.py`** — `BdifApiClient` (search + iter_all) + dataclasses (`BdifItem`, `BdifSociete`, `BdifDocumentFile`) + `parse_item` + `OPERATION_TO_DEAL_TYPE` mapping (OPA→opa, OPAS→opa_simplifiee, OPR→opr, OPRA→opra, OPRRO→opr_ro, OPAGC→garantie_de_cours, etc.).
- [x] **`src/ingestion/amf/bdif_poller.py`** — `BdifPoller.run_once()` orchestrates discovery → atomic PDF download → upsert. Reuses the phase-2 `RateLimiter` (1 req/s + jitter + exp backoff on 429/5xx).
- [x] **Routing change in `src/ingestion/amf/service.py`** — `upsert_deal_from_bdif()` is now the only path that creates deal rows; `record_rss_event()` emits events only when an RSS communiqué matches an existing BDIF deal. **No more synthetic `AMF-SYN-*` refs.**
- [x] **Refactor `src/ingestion/amf/poller.py` (RSS)** — `AmfPoller.run_once()` is now event-only; new `PollResult` exposes `events_emitted` / `duplicates` / `unmatched` / `no_ref` counters.
- [x] **3 BDIF API fixtures** — `tests/fixtures/amf/bdif/page_1_{default,opa,opa_notes}.json` captured live from the real API.
- [x] **44 new tests** (102 total): `test_bdif_api.py` (12), `test_bdif_poller.py` (3 incl. e2e on Fnac Darty), updated `test_service.py` (10 covering BDIF upsert + RSS routing), updated `test_poller.py` (3 covering RSS event-only).
- [x] **Live backfill 2026-05-13** — `python scripts/bdif_run_once.py 60` → **60/60 discovered, 60/60 deals created, 60/60 PDFs downloaded, 0 failures, 0 Akamai 403**. Captured in `artifacts/phase-03/bdif-backfill.txt` (285 lines).

### Brief success criteria

| # | Criterion | Status |
|---|---|---|
| 1 | ≥10 M&A notes discovered from BDIF, last 12 months | ✅ **60** discovered |
| 2 | ≥5 PDFs downloaded + full field extraction | ✅ **60** PDFs, all with `numero`, `target_name`, `deal_type`, `announcement_date`, `source_url`, `pdf_path` populated |
| 3 | Manual validation on Fnac Darty + 2 other deals | ✅ Fnac Darty `226C0644` (142 KB, opa, 2026-05-12), Tarkett `225C0943` (199 KB, opr), Verallia `225C0929` (165 KB, opa) |
| 4 | CI green, coverage ≥80% | ✅ 102 tests pass, **coverage 92%** total (ingestion/amf aggregate 89%) |
| 5 | RSS display/23 still works (no regression) | ✅ `test_rss_poller_emits_event_for_matching_ref` exercises the full RSS pipeline against a known-deal fixture |

### Validation

✅ `VALIDATE PHASE 3` received 2026-05-13. PR [#3](https://github.com/Baptiste6913/ede-platform/pull/3) merged at SHA `52d9c76` on `main` with 8 atomic commits preserved (7 phase-3 + 1 tech-debt-update). Two new tech debt items recorded in `docs/DATA_SOURCES.md`:

1. **Cleanup of 13 leftover `AMF-SYN-*` rows** in prod `ede` DB — **owner phase 4 or 4bis**, low severity (single `DELETE … CASCADE`, log to artifacts).
2. **AMF document type expansion** (DepotOffre / Decisions / CalendrierOffre / PreOffre) — **owner phase 6 or 7**, medium severity (same `BdifPoller` infra, only the `typesDocument` filter changes).

`PreOffre` early-signal handling bundled into item 2 — not split as a separate phase.

---

## Phase 4bis — Cleanup `AMF-SYN-*` legacy rows (closes phase-3 tech debt #1)

### Deliverables checklist

- [x] **`alembic/versions/20260514_0900_0005_cleanup_amf_syn_legacy.py`** — data-only migration: count → `DELETE FROM deals WHERE regulator_ref LIKE 'AMF-SYN-%'`. FK CASCADE drops related events/scores/analyses/paper_positions automatically. No-op when no matching rows exist. Downgrade is a documented manual restore from the pre-cleanup pg_dump.
- [x] **`scripts/backup_db.py`** — reusable pg_dump wrapper writing to `artifacts/{phase}/backup-pre-{reason}-{UTC-timestamp}.sql`.
- [x] **`scripts/cleanup_amf_syn.py`** — three-step runner: (1) SELECT all `AMF-SYN-*` rows + write structured JSON audit to `artifacts/phase-04bis/cleanup-log.txt` BEFORE delete; (2) `alembic upgrade head` to apply migration 0005; (3) verify post-state `count(AMF-SYN-*) == 0` AND `count(orphan events) == 0`.
- [x] **`tests/core/test_migration_0005_cleanup_amf_syn.py`** — 3 integration tests: no-op on clean DB, deletes synthetic rows + cascades events while preserving legit BDIF deals, idempotent on second run.
- [x] **Reversibility verified** — `alembic upgrade head → downgrade base → upgrade head` runs 0001→0005 in both directions against live TimescaleDB pg16.
- [x] **Live run on `ede`** — captured in `artifacts/phase-04bis/run-output.txt`.

### Brief success criteria

| # | Criterion | Status |
|---|---|---|
| 1 | `count(deals AMF-SYN-*)` returns 0 | ✅ 0 |
| 2 | `count(events source='rss_display_23' AND deal_id IN deleted set)` returns 0 | ✅ 0 (no `rss_display_23` events existed; all 60 events are `bdif`) |
| 3 | No orphan events (FK CASCADE) | ✅ verified post-delete via `LEFT JOIN deals` count |
| 4 | Backup snapshot before delete | ✅ `artifacts/phase-04bis/backup-pre-cleanup-20260513T223650Z.sql` (120 KB) |
| 5 | Audit log of deleted rows | ✅ `artifacts/phase-04bis/cleanup-log.txt` (`total_matching_rows: 0` — defensive run, see "Live finding" below) |
| 6 | Tech debt #1 marked CLOSED in `docs/DATA_SOURCES.md` | ✅ updated |

### Live finding

The 13 `AMF-SYN-*` rows from phase-2 live backfill had **already been wiped** by the `DROP DATABASE ede` reset performed at the start of the phase-3 live backfill. The migration runs as a clean no-op on the current `ede` DB (60 BDIF deals, 60 `filing_amf` events with `source='bdif'`, 0 `AMF-SYN-*` rows).

The migration + scripts ship anyway as a **defense-in-depth measure**: any other environment that still carries phase-2 data (e.g. a staging clone preserved before phase 3 backfill) will be cleaned automatically on the next `alembic upgrade head`. The pre-cleanup backup is preserved so the no-op is auditable.

### Validation

Awaiting `VALIDATE PHASE 4bis`.
