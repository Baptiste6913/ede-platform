# Phases — status & validation journal

> Phase progression is **strictly sequential**. Phase N+1 cannot start without `VALIDATE PHASE N` from the user. See `CLAUDE.md` §6.

| # | Phase | Status | Branch | PR | Validated |
|---|---|---|---|---|---|
| 0 | Bootstrap repo & Oracle setup | 🟢 done | `phase-00-bootstrap` | merged ff-only into main | 2026-05-12 |
| 1 | Schema DB & migrations | 🟡 in_progress | `phase-01-schema` | — | — |
| 2 | Poller AMF | ⚪ pending | — | — | — |
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

Awaiting `VALIDATE PHASE 1`.
