# Phases — status & validation journal

> Phase progression is **strictly sequential**. Phase N+1 cannot start without `VALIDATE PHASE N` from the user. See `CLAUDE.md` §6.

| # | Phase | Status | Branch | PR | Validated |
|---|---|---|---|---|---|
| 0 | Bootstrap repo & Oracle setup | 🟢 done | `phase-00-bootstrap` | merged ff-only into main | 2026-05-12 |
| 1 | Schema DB & migrations | 🟢 done | `phase-01-schema` | [#1 merged](https://github.com/Baptiste6913/ede-platform/pull/1) | 2026-05-12 |
| 2 | Poller AMF | 🟡 in_progress | `phase-02-amf-poller` | — | — |
| 3 | Poller Consob | ⚪ pending | — | — | — |
| 4 | Poller BaFin | ⚪ pending | — | — | — |
| 5 | News & marché data | ⚪ pending | — | — | — |
| 6 | Enrichment / PDF parsing & NLP | ⚪ pending | — | — | — |
| 7 | Scoring engine v0 | ⚪ pending | — | — | — |
| 8 | Module Analyst (Claude Code SDK) | ⚪ pending | — | — | — |
| 9 | API FastAPI | ⚪ pending | — | — | — |
| 10 | Streamlit dashboard MVP | ⚪ pending | — | — | — |
| 11 | Alerting Discord | ⚪ pending | — | — | — |
| 12 | Paper trading engine + backtest | ⚪ pending | — | — | — |
| 13 | Deploy Oracle production + monitoring | ⚪ pending | — | — | — |

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

### Validation

Awaiting `VALIDATE PHASE 2`.
