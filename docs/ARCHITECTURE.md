# Architecture — v0 (phase 0)

This document evolves with each phase. v0 captures the data-flow target for phase 1 deliverables.

---

## High-level data flow

```
        ┌────────────────────────────────────────────┐
        │  AMF RSS  │ Consob HTML │ BaFin HTML       │
        │  Newswires│ GDELT BQ    │ DG COMP JSON     │
        └─────┬──────────┬──────────────┬────────────┘
              │          │              │
              ▼          ▼              ▼
        ┌──────────────────────────────────┐
        │      Ingestion (cron + APS)      │
        └──────────────┬───────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────┐
        │  PostgreSQL + TimescaleDB        │
        │  (deals/events/prices/scores/    │
        │   analyses/paper_positions)      │
        └──────┬─────────┬──────────┬──────┘
               │         │          │
               ▼         ▼          ▼
        ┌─────────┐ ┌────────┐ ┌──────────┐
        │Enrichmt │ │Scoring │ │  IBKR    │
        │PDF+NLP  │ │elastic │ │ paper    │
        └────┬────┘ └───┬────┘ └────┬─────┘
             │          │           │
             └──────┬───┴───────────┘
                    ▼
             ┌──────────────┐
             │   Analyst    │
             │ (Claude API) │
             └──────┬───────┘
                    │
        ┌───────────┼───────────────┐
        ▼           ▼               ▼
   ┌────────┐ ┌──────────┐  ┌──────────────┐
   │FastAPI │ │ Discord  │  │  Obsidian    │
   │        │ │ alerts   │  │  vault MD    │
   └────┬───┘ └──────────┘  └──────────────┘
        │
        ▼
   ┌─────────────┐
   │  Streamlit  │
   │  dashboard  │
   └─────────────┘
```

---

## Phase 0 surface

What ships in phase 0:

- `src/core/{settings,logging,db,exceptions}.py` — config (pydantic-settings v2), structlog JSON, async SQLAlchemy engine + `ping()`, typed exception hierarchy.
- `src/api/{main,middleware,routes_health}.py` — FastAPI factory, `CorrelationIdMiddleware`, `GET /health`.
- `Dockerfile` (multi-stage, `python:3.12-slim-bookworm`, ARM64/AMD64) + `docker-compose.yml` (postgres TimescaleDB + redis + app).
- `scripts/oracle_bootstrap.sh` (Ampere ARM provisioning), `scripts/healthcheck_keep_alive.sh` (anti-reclaim cron), `scripts/backup_nightly.sh` (stub).
- `.github/workflows/ci.yml` (matrix: lint + test), `.pre-commit-config.yaml` (ruff + ruff-format + mypy --strict).
- Tests for settings, logging, exceptions, /health (incl. correlation_id echo + degraded path).

Nothing else is wired yet. Ingestion, scoring, analyst, paper engine all land in subsequent phases.

---

## Components (target end-of-phase-13)

| Module | Responsibility | Phase |
|---|---|---|
| `src/core` | settings, logging, db, exceptions | 0 |
| `src/api` | FastAPI routes + middleware | 0, 9 |
| `alembic/` | schema migrations | 1 |
| `src/ingestion/amf` | RSS watcher + BDIF fetcher + parser | 2 |
| `src/ingestion/consob` | HTML scraper + dedup | 3 |
| `src/ingestion/bafin` | HTML scraper + Änderungen logic | 4 |
| `src/ingestion/news` | RSS + GDELT BQ + DG COMP | 5 |
| `src/ingestion/prices` | IBKR live + Stooq EOD fallback | 5 |
| `src/enrichment/pdf_parser` | PyMuPDF + pdfplumber | 6 |
| `src/enrichment/extractors` | FR/IT/DE legal sections | 6 |
| `src/enrichment/nlp` | FinBERT sentiment | 6 |
| `src/scoring` | 15 features → ElasticNet → isotonic calibration | 7 |
| `src/analyst` | Claude SDK wrapper + brief templates | 8 |
| `src/paper` | paper trading engine + journal + backtest | 12 |
| `src/alerting` | Discord webhooks | 11 |
| `src/dashboard` | Streamlit 5 pages | 10 |
| `src/cli` | Typer commands | 8+ |

---

## Container topology

```
┌───────────────────────────────────────────────────┐
│  Oracle Cloud Always Free VM (Ampere ARM, 24GB)   │
│  ┌─────────────────────────────────────────────┐  │
│  │  Docker compose                              │  │
│  │  ┌─────────┐  ┌───────────────┐  ┌────────┐ │  │
│  │  │  app    │  │ postgres+TS   │  │ redis  │ │  │
│  │  │ FastAPI │──│ TimescaleDB   │──│ cache  │ │  │
│  │  │ APS     │  │ pg16          │  │        │ │  │
│  │  └────┬────┘  └───────────────┘  └────────┘ │  │
│  └───────┼───────────────────────────────────────┘  │
│          │                                          │
│   :8000  ▼ (loopback-only port mapping)             │
│  ┌─────────────┐                                    │
│  │   ufw       │   22/tcp (SSH)  8000/tcp (API)    │
│  └─────────────┘                                    │
└───────────────────────────────────────────────────┘
```

---

## Open architectural questions (to track)

1. Volume strategy for `/data/pdfs` on Oracle 200 GB block — bind-mount vs named volume vs object storage. Decision deferred to phase 13.
2. Backup target — Backblaze B2 free tier vs private GitHub release. Decision deferred to phase 13.
3. Streamlit auth — local-only in phase 1 by design (`CLAUDE.md` §7 phase 10). Revisit if remote access becomes needed.
