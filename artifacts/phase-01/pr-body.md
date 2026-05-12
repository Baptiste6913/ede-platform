# Phase 1 — Schema DB & migrations

Branch: `phase-01-schema` → `main`.
Coverage gate: ≥85% on `src/core` (CLAUDE.md §9). **Actual: 100% on 323 statements.**

> **Update (post-validation)**: migration `0004` adds `deals.secondary_jurisdictions jurisdiction_enum[]` and replaces the placeholder `deal_type_enum` (12 v1 values) with the canonical 16-value lowercase legal-terminology list. Seed fixture and tests updated accordingly. Total 44 tests, 0 cosmetic.

---

## Deliverables checklist

- [x] `alembic.ini` — script_location, UTC timezone, file_template, post-write `ruff format` hook
- [x] `alembic/env.py` — **async** env, reads `DATABASE_URL` from `src.core.settings.get_settings()`, `compare_type=True`, `include_object` filters TimescaleDB-managed objects so autogenerate never tries to drop continuous-aggregate views
- [x] `src/core/enums.py` — 11 enum value tuples + `Literal` aliases (single source of truth shared by `models.py` and migration `0001`)
- [x] `src/core/models.py` — 6 SQLAlchemy 2.0 ORM models with `Mapped[T]` / `mapped_column`:
  - `Deal` — 17 cols, unique (`juridiction`, `regulator_ref`), indexes on (`juridiction`, `status`) and (`ticker_target`)
  - `Event` — FK `deal_id` ON DELETE CASCADE, JSONB `raw_payload`, indexes on (`deal_id`, `ts`) and (`event_type`)
  - `Score` — JSONB `features`, check `0 ≤ p_completion ≤ 1`, check on `p_market_implied`, index on (`deal_id`, `ts`)
  - `Analysis` — JSONB `risks` + `catalysts`, FK CASCADE, index on (`deal_id`, `ts`)
  - `PaperPosition` — check `size_eur > 0`, FK CASCADE, indexes on `deal_id` and `status`
  - `Price` — composite PK (`ticker`, `ts`), index on (`ticker`, `ts DESC`) — promoted to **hypertable** in migration 0003
- [x] Migration `0001_create_enums` — 11 `CREATE TYPE … AS ENUM (…)` statements (jurisdiction, deal_type, deal_status, event_type, decision, analyst_verdict, analyst_source, position_side, position_status, currency, price_source); downgrade `DROP TYPE` in reverse order
- [x] Migration `0002_create_main_tables` — `deals`, `events`, `scores`, `analyses`, `paper_positions`; all FKs `ON DELETE CASCADE`; all indexes + check constraints; reuses the ENUM types from `0001` via `create_type=False`
- [x] Migration `0003_prices_hypertable` — `CREATE EXTENSION IF NOT EXISTS timescaledb`, `CREATE TABLE prices`, `create_hypertable(..., chunk_time_interval=>'7 days')`, `CREATE MATERIALIZED VIEW prices_1h WITH (timescaledb.continuous) …`, same for `prices_1d`, `add_continuous_aggregate_policy(...)` for both; downgrade drops aggregates first then the hypertable
- [x] Migration `0004_secondary_jurisdictions_and_deal_type_canonical` — three operations: (a) `ADD COLUMN deals.secondary_jurisdictions jurisdiction_enum[] NULL` for cross-border deals, (b) replace `deal_type_enum` with the canonical 16-value list (CREATE new type → ALTER COLUMN with `USING (CASE…)` v1→v2 mapping → DROP old → RENAME), (c) idempotent `ALTER COLUMN volume DROP NOT NULL` on `prices` (no-op confirmation). Downgrade reverses all three with a best-effort v2→v1 mapping.
- [x] `tests/fixtures/seed_deals.py` — 10 deals: **3 FR** (OPA, OPAS, OPE) + **3 IT** (OPV, OPVS, OPA_IT) + **4 DE** incl. 1 cross-border FR/DE dual-listed (Uebernahmeangebot, Pflichtangebot, Erwerbsangebot, cross-border); mixed statuses: announced, cleared, open, closed, lapsed, withdrawn
- [x] `tests/core/test_models.py` — **22 integration tests** (real PostgreSQL + TimescaleDB):
  - deals: insert/read, update, delete, **unique-constraint violation**, full 10-deals seed distribution, **`secondary_jurisdictions` array roundtrip**, **`secondary_jurisdictions` NULL by default**
  - events: insert/read, JSONB partial update, **cascade-delete with parent deal**
  - scores: insert with features dict, **check-constraint violation** (`p_completion > 1`), history ordered by ts
  - analyses: insert with JSONB lists, update verdict, **cascade-delete**
  - paper_positions: open→close lifecycle, **size_eur check constraint violation**, **cascade-delete**
  - prices: **registered as TimescaleDB hypertable**, OHLCV insert/read, **prices_1h + prices_1d continuous aggregates exist**
- [x] CI updated (`.github/workflows/ci.yml`) — `timescale/timescaledb-ha:pg16` service with healthcheck, `psql` client install, `CREATE EXTENSION timescaledb`, **reversibility step** (`alembic upgrade head → downgrade base → upgrade head`) before pytest
- [x] `docs/PHASES.md` — Phase 0 marked 🟢 done, Phase 1 row 🟡 in_progress with deliverables checklist

---

## Validation outputs

### `ruff check .`

```
All checks passed!
```

### `ruff format --check .`

```
28 files already formatted
```

### `mypy --strict src`

```
Success: no issues found in 12 source files
```

### Reversibility (`alembic upgrade head → downgrade base → upgrade head`)

```
Running upgrade  -> 0001, create postgres enum types
Running upgrade 0001 -> 0002, create main tables (deals, events, scores, analyses, paper_positions)
Running upgrade 0002 -> 0003, create prices table as TimescaleDB hypertable + 1h/1d continuous aggregates
Running upgrade 0003 -> 0004, schema finalisation: secondary_jurisdictions array + canonical deal_type enum

Running downgrade 0004 -> 0003, …
Running downgrade 0003 -> 0002, …
Running downgrade 0002 -> 0001, …
Running downgrade 0001 -> , …

Running upgrade  -> 0001, …
Running upgrade 0001 -> 0002, …
Running upgrade 0002 -> 0003, …
Running upgrade 0003 -> 0004, …
```

4 up + 4 down + 4 up — all idempotent.

### `pytest --cov=src --cov-report=term-missing`

```
collected 44 items

tests/api/test_health.py ....                                            [  9%]
tests/core/test_db.py .........                                          [ 30%]
tests/core/test_exceptions.py ...                                        [ 38%]
tests/core/test_logging.py ...                                           [ 45%]
tests/core/test_models.py ......................                         [ 95%]
tests/core/test_settings.py ...                                          [100%]

------- coverage: platform linux, python 3.12.13 ---------
Name                       Stmts   Miss Branch BrPart  Cover
------------------------------------------------------------
src/__init__.py                0      0      0      0   100%
src/api/__init__.py            0      0      0      0   100%
src/api/middleware.py         22      0      0      0   100%
src/api/routes_health.py      22      0      0      0   100%
src/core/__init__.py           4      0      0      0   100%
src/core/db.py                53      0      8      0   100%
src/core/enums.py             24      0      0      0   100%
src/core/exceptions.py        11      0      0      0   100%
src/core/logging.py           39      0      8      0   100%
src/core/models.py           114      0      0      0   100%
src/core/settings.py          34      0      0      0   100%
------------------------------------------------------------
TOTAL                        323      0     16      0   100%

44 passed in 21.45s
```

22 new DB tests join the 22 from phase 0 → **44 passing**, 0 cosmetic (all tests have ≥1 behavioral assertion — audit in `artifacts/phase-01/tests-audit-output.txt`).

### `docker compose exec postgres psql -d ede_test -c "\dt"`

```
            List of relations
 Schema |      Name       | Type  | Owner
--------+-----------------+-------+-------
 public | alembic_version | table | ede
 public | analyses        | table | ede
 public | deals           | table | ede
 public | events          | table | ede
 public | paper_positions | table | ede
 public | prices          | table | ede
 public | scores          | table | ede
(7 rows)
```

### TimescaleDB internals

```
SELECT hypertable_name, num_dimensions, num_chunks
  FROM timescaledb_information.hypertables;

 hypertable_name | num_dimensions | num_chunks
-----------------+----------------+------------
 prices          |              1 |          0

SELECT view_name, materialization_hypertable_name
  FROM timescaledb_information.continuous_aggregates;

 view_name | materialization_hypertable_name
-----------+---------------------------------
 prices_1d | _materialized_hypertable_12
 prices_1h | _materialized_hypertable_11
```

### Postgres ENUM types

```
SELECT typname FROM pg_type WHERE typcategory='E' ORDER BY typname;

       typname
----------------------
 analyst_source_enum
 analyst_verdict_enum
 currency_enum
 deal_status_enum
 deal_type_enum
 decision_enum
 event_type_enum
 jurisdiction_enum
 position_side_enum
 position_status_enum
 price_source_enum
(11 rows)
```

---

## Notable design choices

1. **Async alembic with subprocess migration in tests.** `env.py` uses `asyncio.run(run_async_migrations())` which works fine from CLI but not from inside an already-running event loop (i.e. pytest-asyncio test fixtures). The session-scoped `_migrate_once` fixture invokes `alembic` via `subprocess.run`, side-stepping the nested-loop problem. Function-scoped `db_engine` is re-created per test so asyncpg's Futures bind to the correct loop.
2. **Postgres-native ENUM, not Python enums.** Per CLAUDE.md "Enum types Postgres pour status, deal_type, event_type, decision (pas Python enum côté DB)". `src/core/enums.py` exposes `Literal` aliases for typing — the ORM uses `sqlalchemy.Enum(*VALUES, name=…, create_type=False)`, and migration `0001` is the single source of truth for the actual `CREATE TYPE` statements.
3. **Continuous aggregates with `WITH NO DATA`.** Aggregates are created empty; the `add_continuous_aggregate_policy` calls set up background refresh in production. In CI/tests the aggregate-existence test still passes — the policies just don't run because no Timescale background worker is attached to the ephemeral test database.
4. **Chunk interval = 7 days** for the prices hypertable. With phase 5's IBKR 5-minute snapshots on ~10-20 active deals, a 7-day chunk stays under ~50k rows — comfortable for Timescale's default tuning.
5. **`Decimal` everywhere for monetary fields**, never `float`. Precisions are tuned to brief use cases (offer_price 18,6; pnl_eur 14,2; p_completion 6,5).
6. **All FKs to deals.id are `ON DELETE CASCADE`** AND the ORM `relationship` adds `cascade="all, delete-orphan"` + `passive_deletes=True` so the Python side cooperates with the DB CASCADE rather than fighting it.

---

## Limitations connues / dette technique acceptée

1. **No `models.py` test for the ORM relationships.** The relationships (`Deal.events`, etc.) are exercised indirectly via the cascade-delete tests. A direct `await session.refresh(deal, ["events"])` test would be nice — deferred to phase 2 when the AMF poller starts writing real event rows.
2. **No price seed fixture.** The brief says "10 deals" only; price data lives in `prices` hypertable but no fixture seed yet. Phase 5 (IBKR + Stooq) will populate this. The hypertable insert/read test uses one inline `Price` row.
3. **CI does not yet validate the production `compose-up` path end-to-end.** Reversibility is checked, but a smoke test of `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` is deferred to phase 13.
4. **Refresh policy on aggregates assumes TimescaleDB background workers.** Oracle Always Free will have them; CI ephemeral DB won't. Aggregates stay empty in CI — acceptable since phase 1 only tests their existence.
5. **JSONB schema is unconstrained at the DB layer.** `raw_payload`, `features`, `risks`, `catalysts` accept any structure. Validation happens in Pydantic models (to land in phase 2+). Acceptable as a phase 1 baseline.
6. **`alembic_version` table not in ORM metadata.** Standard Alembic behaviour — won't show up in autogenerate diffs. No action required.

---

## Architectural Q&A (resolved post-review)

1. **Cross-border deal modelling** → 1 canonical deal + `deals.secondary_jurisdictions jurisdiction_enum[]`. Implemented in migration `0004`. Tested via the Rho Technologies SE seed row.
2. **`deal_type_enum`** → kept as a single unified enum, with the v1 12-value placeholder list replaced by the **canonical 16-value lowercase legal-terminology list** in migration `0004`. Cross-jurisdiction tag mismatch (e.g. tagging a FR filing with `pflichtangebot`) remains a soft constraint — could be hardened with a future check constraint coupling `juridiction` and `deal_type` ranges. Deferred until real ingestion shows it's needed.
3. **`prices.volume`** → NULLABLE (`BIGINT NULL`) confirmed. Migration `0004` re-asserts this with an idempotent `ALTER COLUMN … DROP NOT NULL` (no-op against the current state, but documents the choice in the migration trail).
4. **Refresh policy** (30min on 1h aggregate, 1h on 1d aggregate) → accepted, will revisit in phase 12 only if backtests demand tighter freshness.

## Post-0004 schema state (artifacts/phase-01/)

- `alembic-current.txt` → `version_num = 0004`
- `psql-deal-types.txt` → 16 canonical values (FR opa/opa_simplifiee/opa_obligatoire/ope/opas/opra/opr/opr_ro/garantie_de_cours, IT opa_volontaire_totalitaria/opa_volontaire_parziale/opa_consolidamento, DE pflichtangebot/freiwilliges_uebernahmeangebot/delisting_erwerbsangebot/erwerbsangebot)
- `psql-prices-columns.txt` → `volume bigint YES (nullable)`
- `deals.secondary_jurisdictions` → `ARRAY of _jurisdiction_enum, nullable=YES`

---

## Conventional commits in this branch

```
feat(core): add enums.py with 11 Literal aliases and value tuples
feat(core): add 6 SQLAlchemy 2.0 ORM models (Deal, Event, Score, Analysis, PaperPosition, Price)
feat(alembic): configure async env + script template + alembic.ini
feat(migrations): add 0001 enums, 0002 main tables, 0003 prices hypertable + aggregates
test(fixtures): add 10-deals seed (FR/IT/DE + cross-border) and integration test infra
test(models): add 20 CRUD + cascade + unique + check + hypertable tests
chore(ci): add timescaledb service + reversibility step to test job
docs(phases): mark phase 0 done, phase 1 in_progress with checklist
feat(core): canonical deal_type enum (16 values) + secondary_jurisdictions
feat(migrations): add 0004 (deal_type canonical + secondary_jurisdictions)
test: update seed_deals to canonical deal_type + 2 new array tests
docs(phase-01): refresh artifacts after migration 0004
```
