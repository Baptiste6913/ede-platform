# Dashboard — Phase 7 MVP

**Status:** V1 single-file Streamlit. 5 pages, 6 global filters, served read-only from the live `ede` DB. **NOT** a paper-trading interface — the Paper Portfolio page is a UX preview only (mock data, no IBKR connection).

## Run it

```bash
# 1) Make sure docker compose postgres is up + alembic head=0010
docker compose up -d postgres
alembic upgrade head

# 2) Make sure the latest scoring run is in the DB
python scripts/score_deals_run.py

# 3) Launch
streamlit run streamlit_app.py
# default → http://localhost:8501
```

Override the DB target via `DATABASE_URL` if you don't want the project default (handy for spinning up against a snapshot in CI demos):

```bash
DATABASE_URL=postgresql+asyncpg://ede:ede@localhost:5432/ede streamlit run streamlit_app.py
```

The dashboard prefers the **sync psycopg** driver under the hood (Streamlit + asyncio is awkward), but consumes the same `DATABASE_URL` env as the rest of the platform — the data layer auto-converts `+asyncpg` → `+psycopg`.

## Pages

| # | Page | What it shows |
|---|---|---|
| 1 | 🏠 Overview | 4 KPI cards, jurisdiction × star heat-map, top-5 high-conviction, top-5 watchlist, recent 7-day activity |
| 2 | 📋 Deals List | Sortable table (st.dataframe) of every scored cluster, CSV export, drill-down selector |
| 3 | 🔍 Deal Detail | Score header (★ badge + p + decision + status), top-3 positive / risk factors, identity table, sub-filings expander, events timeline, document links, local notes textarea |
| 4 | 📊 Analytics | Score histogram, calibration plot, feature importance bar, pipeline timeline, class balance pie |
| 5 | 💼 Paper Portfolio (preview) | **MOCK** positions / risk metrics + watchlist — Phase 8 will replace with real IBKR data |

Navigation: left sidebar radio. Selecting a deal from Overview's Top-5 or from the Deals List's drill-down selector sets `st.session_state["selected_cluster"]` and jumps to Deal Detail.

## Global filters

A single `DealsFilters` dataclass (`src/dashboard/data.py`) drives every page that reads rows / charts. Filters live in `st.session_state` and are encoded into a JSON key for `@st.cache_data(ttl=300)` so identical filter combos hit the cache.

| Filter | Default | Notes |
|---|---|---|
| Jurisdiction | all | Multi-select FR/IT/DE |
| Score ★ | 3 / 4 / 5 | Multi-select 1..5 |
| Status | all | all / pending / closed / failed (uses `deals.completion_label`) |
| Announcement date | today−730d → today | Streamlit date range widget |
| Acquirer type | all | Multi-select from `scores.features['acquirer_type']` |
| Deal type | all | Multi-select 18-value enum (Phase-5 includes `delisting_offer` + `prohibition_ungenutzt`) |

The sidebar footer shows `alembic_version`, current `model_version`, and the timestamp of the latest scoring run. Click **↻ Refresh data** to bust the cache.

## Architecture

```
streamlit_app.py                 (~470 lines, single-file)
└── src/dashboard/
    ├── __init__.py              (public surface, re-exports)
    ├── data.py                  (SQLAlchemy + psycopg, returns pd.DataFrame)
    ├── scoring_helpers.py       (badge / star / color formatters — pure)
    ├── charts.py                (Plotly figure builders — pure)
    └── paper_portfolio_mock.py  (DB-backed mock for Phase 8 preview)

tests/dashboard/
    ├── test_data.py             (integration, real DB)
    ├── test_scoring_helpers.py  (unit, pure functions)
    ├── test_charts.py           (unit, Plotly Figure structure)
    └── test_paper_portfolio_mock.py (mixed unit + integration)
```

Why split data out of the single-file? **Testability.** The data layer has no Streamlit imports, so pytest can exercise every query against a real `db_session` fixture without spinning up Streamlit. The streamlit_app.py top of the file just adds the `@st.cache_data` wrappers + the page-routing main loop.

## Cluster semantics

The dashboard's "cluster" is the unit Phase 6 produced via the FR multi-stage collapse:
- For IT / DE: 1 cluster = 1 `deals` row = 1 underlying M&A operation.
- For FR: 1 cluster = N `deals` rows sharing `(target_name, juridiction='FR')` and chronologically contiguous within 730 days. The scoring V1 picked the earliest deal_id in each cluster as the representative.

`scores.deal_id` always points to the representative. Drill-down on a cluster fetches every sibling via `SELECT * FROM deals WHERE target_name = X AND juridiction = Y` so the FR chain is reconstructible at view time.

## Manual notes — V1 local JSON

Each Deal Detail page exposes a free-form textarea, persisted to:

```
data/notes/{cluster_id}.json
```

`data/` is gitignored entirely (existing rule from Phase 0). **Single-user assumption.** No notion of locking, history, or sync.

**Tech debt:** when multi-user / auth ship in V2 (Next.js rewrite at Phase 12, or earlier if needed), migrate notes to a dedicated DB table (`cluster_notes`, migration 0011). Until then the local JSON is the pragmatic choice — zero schema overhead, instant save, survives Streamlit reloads.

## Known V1 limitations

| # | Item | Phase to fix |
|---|---|---|
| 1 | Spread column on Deals List is a placeholder (`Φ`) — no live cours data yet | 9 (IBKR + Stooq) |
| 2 | Paper Portfolio = mock only (3 hardcoded 5★ deals + fabricated P&L) | 8 (IBKR Paper Trading) |
| 3 | Manual notes are local JSON, not synced anywhere | 11/12 (migration 0011 + multi-user) |
| 4 | Cluster definition is implicit (no `deals.cluster_id` column) — joins go through `(target_name, juridiction)` strings | 7 tech-debt list (migration 0011) |
| 5 | Recent activity list only walks the filtered set — no notion of "anything new since last visit" | 12 (Next.js + websocket) |
| 6 | Feature importance reads the **latest** `models/scoring_v1_*.pkl`; if multiple PKLs exist, the dashboard always picks the newest by lexical sort. | 8 (model registry) |

## Performance

Page load on the live 329-cluster snapshot:
- Cold load (cache empty): ~1.8 s (1 SQL round-trip on Overview, 1 model load on Analytics).
- Warm load (cache hit, TTL ≤ 5 min): ~0.3 s.

Well under the 3-second target in the Phase-7 brief. `@st.cache_data(ttl=300)` covers the hot paths; the global "↻ Refresh data" button clears the cache when the user re-runs `score_deals_run.py` and wants the new run live without restarting Streamlit.

## Roadmap V2

The dashboard will be **rewritten in Next.js + FastAPI** at Phase 12, after the paper-trading engine ships and we have real ledger data to display. Streamlit's strength is rapid iteration during the calibration phase (now); the limitations (single-user, no auth, hard to add per-user state, awkward custom CSS) make it the wrong long-term host once positions are real and decisions are auditable.

**Phase 8 enhancements (still on Streamlit) before the rewrite:**
- Replace Paper Portfolio mock with the real IBKR ledger view (positions, fills, daily P&L) — keep the same page layout.
- Live cours data fills the `spread` column on Deals List + adds a "spread vs offer" mini-chart on Deal Detail.
- `events_count` aggregation moves from runtime SQL to a `deals.cluster_id` column populated by a backfill migration.

**Phase 11 (Discord alerts):**
- Sidebar adds an "alerts" feed (last N Discord webhook payloads).
- Watchlist learns to *fire* on triggers (price crosses entry, FDI clearance event, etc.).

**Phase 12 (Next.js rewrite):**
- Multi-user auth (NextAuth + email magic-link).
- Per-user portfolio + watchlist persisted in DB (migration 0011).
- Per-user notes (migration 0011).
- Realtime updates via WebSocket subscription to `scores.ts` change-stream.
- Mobile-friendly layout.
