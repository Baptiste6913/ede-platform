# Phases — status & validation journal

> Phase progression is **strictly sequential**. Phase N+1 cannot start without `VALIDATE PHASE N` from the user. See `CLAUDE.md` §6.

| # | Phase | Status | Branch | PR | Validated |
|---|---|---|---|---|---|
| 0 | Bootstrap repo & Oracle setup | 🟡 in_progress | `phase-00-bootstrap` | — | — |
| 1 | Schema DB & migrations | ⚪ pending | — | — | — |
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

Awaiting `VALIDATE PHASE 0`.
