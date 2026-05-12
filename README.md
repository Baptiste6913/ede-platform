# EDE — Event-Driven Europe

Proprietary platform for detection, scoring, and **paper trading** of European M&A operations (OPA/OPE) — FR (AMF), IT (Consob), DE (BaFin).

Phase 1 scope: paper trading only, zero real capital, ~8–10h/week effort cap. See `CLAUDE.md` for the full build brief.

> Status: **Phase 0 — Bootstrap repo & Oracle setup** (in_progress)

---

## Quickstart

### Local dev

Requires Docker Desktop (or Docker Engine + compose plugin) and `git`.

```bash
git clone <repo-url> ede-platform
cd ede-platform
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0","uptime_seconds":1.23,"db":{"ok":true,"latency_ms":2.1}}
```

Stop:

```bash
docker compose down
```

Logs (structured JSON):

```bash
docker compose logs -f app
```

Native Python (no Docker):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
uvicorn src.api.main:app --reload
```

### Tests / lint

```bash
pytest --cov=src --cov-report=term-missing
ruff check .
ruff format --check .
mypy src
```

### Oracle deploy (stub — full impl phase 13)

Phase 0 ships the bootstrap script only; production deploy is finalized in phase 13.

```bash
# On the Oracle Ampere ARM VM (Ubuntu 22.04 LTS):
curl -fsSL https://raw.githubusercontent.com/<user>/ede-platform/main/scripts/oracle_bootstrap.sh | bash
# Log out / back in (docker group), then:
cd ~/ede-platform && cp .env.example .env && docker compose up -d
```

The bootstrap script installs Docker, configures ufw (allow 22/8000), fail2ban, unattended-upgrades, and the anti-reclaim keep-alive cron (`scripts/healthcheck_keep_alive.sh`).

---

## Repo layout

See `docs/ARCHITECTURE.md`. Top level:

```
src/         core / api / ingestion / enrichment / scoring / analyst / paper / dashboard / cli
tests/       mirror of src/
docs/        ARCHITECTURE, PHASES, DATA_SOURCES, SCORING_MODEL, JURIDICTIONS, whitepaper_ede
scripts/     oracle_bootstrap, healthcheck_keep_alive, backup_nightly
alembic/     migrations (populated phase 1)
data/        gitignored — pdfs, snapshots, models
```

---

## Phase status

See `docs/PHASES.md`.

| Phase | Title | Status |
|---|---|---|
| 0 | Bootstrap repo & Oracle setup | 🟡 in_progress |
| 1–13 | … | ⚪ pending |

---

## Conventions

- Python 3.12, FastAPI, async SQLAlchemy 2.0, PostgreSQL 16 + TimescaleDB, structlog JSON.
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`).
- pre-commit hooks: ruff (lint+format) + mypy --strict.
- CI: GitHub Actions, lint + test jobs in parallel, pip cache.
- `pytest --cov` ≥80% by default, ≥85% on ingestion/API/models.
- No real network in CI; HTTP fixtures live in `tests/fixtures/{module}/`.

---

## License

Proprietary. © Baptiste Bouault, 2026.
