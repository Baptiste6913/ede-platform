# Phase 4bis — Cleanup `AMF-SYN-*` legacy rows

Closes phase-3 tech debt item #1 (recorded in `docs/DATA_SOURCES.md`).

Branch: `phase-04bis-cleanup-amf-syn` → `main`.
Migration: `0005_cleanup_amf_syn_legacy`. Reversibility: data-only (manual restore from pg_dump documented in the migration docstring).

---

## TL;DR

The 13 `AMF-SYN-*` rows that phase-2 RSS poller injected into `ede` had **already been wiped** by the `DROP DATABASE ede` reset performed at the start of phase-3's live BDIF backfill. This PR ships the migration + scripts anyway as a defense-in-depth measure for any other environment that still carries phase-2 data — `alembic upgrade head` will silently delete `AMF-SYN-*` rows wherever they exist, and is a clean no-op otherwise.

| Live state on `ede` (2026-05-14) | Value |
|---|---|
| `count(deals WHERE regulator_ref LIKE 'AMF-SYN-%')` pre-run | 0 |
| Deleted by migration | 0 |
| Backup pre-cleanup | `artifacts/phase-04bis/backup-pre-cleanup-20260513T223650Z.sql` (120 KB) |
| Audit log | `artifacts/phase-04bis/cleanup-log.txt` (`total_matching_rows: 0`) |
| Run trace | `artifacts/phase-04bis/run-output.txt` |
| `count(orphan events)` post-run | 0 |
| Total BDIF deals preserved | 60 |

---

## Brief success criteria — all green

| # | Criterion | Status |
|---|---|---|
| 1 | `count(deals AMF-SYN-*)` returns 0 | ✅ |
| 2 | `count(events.source='rss_display_23' AND deal_id IN deleted set)` returns 0 | ✅ (no `rss_display_23` events existed; all 60 events are `bdif`) |
| 3 | No orphan events (FK CASCADE) | ✅ verified via `LEFT JOIN deals` post-delete count |
| 4 | Backup snapshot before delete | ✅ 120 KB pg_dump |
| 5 | Audit log of deleted rows | ✅ structured JSON with row catalog (empty in this run) |
| 6 | Tech debt #1 marked CLOSED in `docs/DATA_SOURCES.md` | ✅ updated |

---

## Deliverables

- **`alembic/versions/20260514_0900_0005_cleanup_amf_syn_legacy.py`** — data-only migration. Counts before deleting (no-op fast path on clean DBs), then `DELETE FROM deals WHERE regulator_ref LIKE 'AMF-SYN-%'`. FK `ON DELETE CASCADE` (from migration 0002) handles related events/scores/analyses/paper_positions automatically. Reversibility: data-only, downgrade is a documented manual restore from the pre-cleanup pg_dump.
- **`scripts/backup_db.py`** — reusable pg_dump wrapper. Writes to `artifacts/{phase}/backup-pre-{reason}-{UTC-timestamp}.sql` with the right `--no-owner --format=plain` for portability.
- **`scripts/cleanup_amf_syn.py`** — three-step orchestrator: capture pre-state audit JSON → invoke `alembic upgrade head` → verify post-state. Exit code 0 only when `count(AMF-SYN-*) == 0` AND `count(orphan events) == 0`.
- **`tests/core/test_migration_0005_cleanup_amf_syn.py`** — 3 integration tests:
  - `test_cleanup_is_noop_on_clean_db` — exercising the fast path
  - `test_cleanup_deletes_synthetic_rows_and_cascades_events` — pre-seed 1 legit BDIF deal + 1 legacy AMF-SYN deal with 2 events, run delete, assert only the legacy deal + its 2 events are gone, the legit deal + its 1 event survive
  - `test_cleanup_is_idempotent` — re-running the DELETE after first cleanup is harmless

---

## Validation outputs

### `pytest --cov`

```
105 passed in 45.23s
TOTAL                                1015     67    160     20    92%
```

(102 phase-3 tests + 3 new migration tests = 105 total; coverage unchanged at 92%.)

### Reversibility

```
alembic downgrade base   # 0005 → 0004 → 0003 → 0002 → 0001 → base
alembic upgrade head     # base → 0001 → 0002 → 0003 → 0004 → 0005
```

All five steps run cleanly in both directions against `timescale/timescaledb-ha:pg16`.

### Live run

```
[1/3] captured 0 AMF-SYN-* rows → artifacts/phase-04bis/cleanup-log.txt
[2/3] alembic upgrade head → 0005 applied
[3/3] post-state: remaining AMF-SYN-*=0, orphan events=0
OK deleted=0 pre_count=0 remaining=0 orphan_events=0
```

`alembic_version` is now `0005` on `ede`.

---

## Notable design choices

1. **Defensive no-op fast path.** The migration `count()`s before `DELETE` and short-circuits when nothing matches. This makes `alembic upgrade head` safe to run on any environment regardless of its prior history.
2. **No downgrade restore baked into the migration.** Data-only migrations can't be reversed via Alembic logic alone. The docstring documents the manual restore path (`psql < backup-pre-cleanup-*.sql`).
3. **Backup file kept under `artifacts/phase-04bis/`** — under `.gitignore`'s `artifacts/*` exclusion via `!artifacts/phase-*/` negation, so it ships in the PR for auditability.
4. **`scripts/backup_db.py` is generic.** Takes `--phase` and `--reason` flags. Will be reused for any future destructive migration in phases 4-14.

---

## Limitations connues

1. **Migration 0005 is intentionally one-directional.** Downgrading from 0005 to 0004 leaves the deleted rows gone. This is acceptable because (a) `AMF-SYN-*` rows were noise, (b) the pre-cleanup backup is preserved per-environment.
2. **`scripts/cleanup_amf_syn.py` requires `DATABASE_URL`** in the environment (no CLI flag). Documented in its docstring; standard pattern across the repo.

---

## Conventional commits

```
feat(alembic): add migration 0005_cleanup_amf_syn_legacy
feat(scripts): add backup_db.py + cleanup_amf_syn.py
test(migrations): 3 integration tests for migration 0005
docs: close tech debt #1 in DATA_SOURCES.md + Phase 4bis row in PHASES.md
chore(artifacts): record live cleanup run on ede DB
```
