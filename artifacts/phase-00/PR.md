# Phase 0 — Bootstrap

> Generated locally because `gh` CLI is not installed on this Windows host. Open the PR by hand with this body once the repo is pushed to GitHub.

Branch: `phase-00-bootstrap` → `main`
Coverage gate: ≥80% (CLAUDE.md §9). **Actual: 100% on 185 statements.**

---

## Deliverables checklist

- [x] `scripts/oracle_bootstrap.sh` — Ampere ARM provisioning (Docker + ufw + fail2ban + unattended-upgrades + keep-alive cron install)
- [x] `Dockerfile` — multi-stage `python:3.12-slim-bookworm`, non-root user, tini, HEALTHCHECK
- [x] `docker-compose.yml` — services `postgres` (`timescale/timescaledb-ha:pg16`), `redis`, `app`; loopback-only port mapping
- [x] `pyproject.toml` — minimal deps (fastapi, uvicorn, sqlalchemy[asyncio], alembic, asyncpg, structlog, pydantic-settings, httpx, typer, redis) + dev (pytest, pytest-asyncio, pytest-cov, ruff, mypy, pre-commit)
- [x] `src/core/settings.py` — pydantic-settings **v2** with `SettingsConfigDict`, `SecretStr` for tokens, `lru_cache` singleton
- [x] `src/core/logging.py` — structlog **JSON** + `correlation_id` contextvar, stdlib `LoggerFactory`, idempotent `configure_logging`
- [x] `src/core/db.py` — async SQLAlchemy 2.0 engine + sessionmaker + `session_scope()` + `ping()` + `dispose_engine()`
- [x] `src/core/exceptions.py` — typed hierarchy (`EDEError`, `ConfigurationError`, `DatabaseError`, `ExternalServiceError`, `RateLimitError`, `NotFoundError`)
- [x] `src/api/main.py` — FastAPI factory + lifespan (logging on startup, engine disposal on shutdown)
- [x] `src/api/middleware.py` — `CorrelationIdMiddleware` (reads `X-Correlation-Id`, generates UUID4 if absent, echoes on response, binds to structlog contextvars)
- [x] `src/api/routes_health.py` — `GET /health` → `{status, version, uptime_seconds, db: {ok, latency_ms, error}}`
- [x] `scripts/healthcheck_keep_alive.sh` — 5 min nice-19 CPU activity, JSON audit log, cron-installed every 6h
- [x] `scripts/backup_nightly.sh` — explicit phase-13 stub (logs that it ran, no real backup yet)
- [x] `.github/workflows/ci.yml` — matrix `{lint, test}` running in parallel, `pip` cache via `actions/setup-python@v5`, coverage XML artifact
- [x] `.pre-commit-config.yaml` — pre-commit hooks (yaml/toml/large-files), **ruff + ruff-format**, **mypy --strict** with pydantic/sqlalchemy/structlog stubs
- [x] `README.md` — quickstart "Local dev" + "Oracle deploy" (deploy section flagged as phase-13 stub)
- [x] `docs/ARCHITECTURE.md` v0 — ASCII data-flow diagram (copied verbatim from CLAUDE.md §10.B) + container topology + module ownership table
- [x] `docs/PHASES.md` — 14-row phases table, Phase 0 row marked 🟡 in_progress with full deliverables checklist

---

## Validation outputs

### `ruff check .`

```
All checks passed!
```

### `ruff format --check .`

```
19 files already formatted
```

### `mypy --strict src`

```
Success: no issues found in 10 source files
```

### `pytest --cov=src --cov-report=term-missing`

```
======================== test session starts =========================
platform linux -- Python 3.12.13, pytest-8.3.4, pluggy-1.6.0
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.13.0, asyncio-0.24.0, cov-6.0.0
asyncio: mode=Mode.AUTO, default_loop_scope=function
collected 22 items

tests/api/test_health.py ....                                  [ 18%]
tests/core/test_db.py .........                                [ 59%]
tests/core/test_exceptions.py ...                              [ 72%]
tests/core/test_logging.py ...                                 [ 86%]
tests/core/test_settings.py ...                                [100%]

-------- coverage: platform linux, python 3.12.13 ---------
Name                       Stmts   Miss Branch BrPart  Cover
------------------------------------------------------------
src/__init__.py                0      0      0      0   100%
src/api/__init__.py            0      0      0      0   100%
src/api/middleware.py         22      0      0      0   100%
src/api/routes_health.py      22      0      0      0   100%
src/core/__init__.py           4      0      0      0   100%
src/core/db.py                53      0      8      0   100%
src/core/exceptions.py        11      0      0      0   100%
src/core/logging.py           39      0      8      0   100%
src/core/settings.py          34      0      0      0   100%
------------------------------------------------------------
TOTAL                        185      0     16      0   100%

========================== 22 passed in 5.23s ========================
```

### `docker compose ps`

```
NAME           IMAGE                           SERVICE    STATUS                        PORTS
ede-app        ede-platform-app                app        Up About a minute (healthy)   127.0.0.1:8000->8000/tcp
ede-postgres   timescale/timescaledb-ha:pg16   postgres   Up About a minute (healthy)   127.0.0.1:5432->5432/tcp
ede-redis      redis:7-alpine                  redis      Up About a minute (healthy)   127.0.0.1:6379->6379/tcp
```

All three containers reach `(healthy)` (Docker HEALTHCHECK on app, native healthcheck on pg/redis).

### `curl -i -H "X-Correlation-Id: phase-00-validate" http://localhost:8000/health`

```
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json
x-correlation-id: phase-00-validate

{"status":"ok","version":"0.1.0","uptime_seconds":105.84,"db":{"ok":true,"latency_ms":4.06,"error":null}}
```

Correlation-id echo is verified end-to-end. DB ping resolves through async SQLAlchemy → TimescaleDB pg16 in ~4 ms.

### `curl http://localhost:8000/docs` and `/openapi.json`

OpenAPI 3.1 spec is auto-generated. `/docs` returns the Swagger UI (200 OK, `text/html`).

---

## Limitations connues / dette technique acceptée

1. **No real GitHub PR opened in this PR body.** The Windows host running Claude Code does not have `gh` CLI installed. The branch `phase-00-bootstrap` is created locally and ready to push manually:
   ```
   git remote add origin git@github.com:<user>/ede-platform.git
   git push -u origin main
   git push -u origin phase-00-bootstrap
   gh pr create --title "Phase 0 — Bootstrap" --body-file artifacts/phase-00/PR.md
   ```
2. **Docker images built on host AMD64, not ARM64.** Local validation runs `python:3.12-slim-bookworm` (multi-arch, AMD64 selected by Docker Desktop). The Dockerfile is ARM64-compatible — verified by the `python:3.12-slim-bookworm` tag manifest list — but phase 13 will rebuild on the Oracle Ampere VM to confirm.
3. **`oracle_bootstrap.sh` is not idempotent on every step.** UFW reset, fail2ban install, etc. are safe to re-run. Docker install detects existing installs. But re-running on a heavily customized host may surprise — the script targets a fresh Ubuntu 22.04 minimal image.
4. **`backup_nightly.sh` is a stub.** Per CLAUDE.md §7 phase 13, full backup (pg_dump + tar of `/data/pdfs` → B2 / private release) lands in phase 13. Phase 0 only ships the cron wiring shape.
5. **CI runs on `ubuntu-latest` (AMD64).** ARM64 CI matrix is not added — GitHub free tier ARM runners are scarce and slow. Acceptable for phase 1; revisit if cross-arch regressions ever appear.
6. **`src/core/db.py` test coverage is 100% via mocks**, not a real DB. A live-DB integration test lands in phase 1 (Alembic migration tests need an actual pg).
7. **No `EDE_API_TOKEN` auth on `/health`.** By design — health is a public liveness probe. Auth lands in phase 9 for protected routes.
8. **WSL note (Finance-V4 alignment).** This repo runs entirely inside Docker; no direct WSL dependency. If the user prefers running uvicorn on the host (Linux) the `pip install -e ".[dev]"` path in README works inside any 3.12 venv.

---

## Questions ouvertes pour l'utilisateur

1. **GitHub repo creation.** Should I (a) wait for the user to create `ede-platform` on GitHub and provide the URL, or (b) skip GitHub for phase 0 and tag the local commit as the validation artifact?
2. **`gh` CLI install.** Worth installing `gh` on the Windows host to automate PR creation for phases 1-13? Or keep PR creation manual?
3. **Oracle VM provisioning.** Phase 0 ships the bootstrap script, not a provisioned VM. Should phase 13 (the actual deploy phase) be the one to do the `oci compute instance launch` step, or do we want it provisioned earlier so phases 2-5 pollers can run in-place?
4. **Discord webhook.** The `.env.example` has placeholders. Phase 11 will need real webhook URLs. Recycle from Finance-V4 or create new channels per CLAUDE.md §10.A?

---

## Conventional commits in this branch

```
feat(infra): add Dockerfile, docker-compose, pyproject for phase 0
feat(core): add settings, logging, db, exceptions modules
feat(api): add FastAPI app with /health and correlation-id middleware
feat(scripts): add Oracle bootstrap + anti-reclaim keep-alive + backup stub
chore(ci): add GitHub Actions workflow and pre-commit hooks
test: add core + api tests with 100% coverage
docs: add README, ARCHITECTURE v0, PHASES journal
```

(One commit per group, atomic, no `wip` or `various fixes`.)
