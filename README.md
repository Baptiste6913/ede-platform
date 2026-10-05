# EDE (Event-Driven Europe)

EDE estimates the probability that a European takeover bid completes and turns that estimate into paper-trading decisions for merger arbitrage. It reads the filings published by the French, German, and Italian market regulators.

## Run it

Requires Docker and Git. This starts PostgreSQL with TimescaleDB, Redis, and the API.

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/health
```

Apply the schema, then start the Streamlit dashboard on `http://localhost:8501`:

```bash
alembic upgrade head
streamlit run streamlit_app.py
```

Without Docker for the app itself (Python 3.12):

```bash
pip install -e ".[dev]"
uvicorn src.api.main:app --reload
```

Backfill filings, then train and score:

```bash
python scripts/bdif_run_once.py          # AMF (FR)
python scripts/bafin_run_once.py         # BaFin (DE)
python scripts/consob_run_once.py        # Consob (IT), needs SCRAPINGBEE_API_KEY
python scripts/score_deals_run.py
```

Run one daily trading cycle against an IBKR paper gateway:

```bash
python scripts/run_trading.py --once
```

Tests and checks:

```bash
pytest
ruff check . && ruff format --check .
mypy src
```

## Architecture

- `src/ingestion/{amf,bafin,consob}`: one poller, fetcher, and parser per regulator. Each writes deals and filing events to PostgreSQL.
- `src/core`: settings, structured logging, async SQLAlchemy models, typed exceptions. `alembic/` holds 17 migrations.
- `src/pricing`: resolves ISINs to tickers through OpenFIGI and fetches reference prices from yfinance.
- `src/scoring`: deal features (bid premium, relative size, acceptance threshold, payment type, jurisdiction, sector, and others in `features.py`) feed an elastic-net logistic regression with isotonic calibration. The output is a completion probability mapped to 1 to 5 stars.
- `src/trading`: decision engine (spread, fractional Kelly sizing, stop and take-profit), bracket orders through `ib_async`, and safeguards (kill switch file, daily loss limit, position cap, order cooldown, manual approval for the first 5 trades).
- `src/output`: writes one Markdown decision file per tradable deal. `src/dashboard` and `streamlit_app.py` serve a read-only 5-page view of the database.
- `src/api`: FastAPI app with a `/health` route and correlation-ID middleware.

## Stack

Python 3.12, FastAPI, SQLAlchemy 2.0 (asyncio), asyncpg, Alembic, PostgreSQL 16 with TimescaleDB, Redis, APScheduler, PyMuPDF, scikit-learn, Streamlit, Plotly, ib_async, yfinance, structlog, Docker. Quality gates are pytest, ruff, and mypy in strict mode, run by GitHub Actions.

## Status

Paper trading only. `IbkrClient` refuses to connect unless the paper flag is set and the port is 7497 or 4002.

The latest merged work (`docs/phase-14/closure_summary.md`) ran the full pipeline on fresh French and German offers and produced one tradable decision. The scoring model was trained on 128 labeled clusters, so it separates deal types more than individual deals. `docs/PHASES.md` lags the code and still lists later phases as pending.
