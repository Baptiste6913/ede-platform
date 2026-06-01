# Phase 9.2 02b — Step 1i DB update audit

Records the transactional UPDATE applied to the 64 FR `verified_cash`
deals flagged `CORRECTED` by Step 1h. Single transaction, all-or-nothing.

## 1. Backup (pre-update)

- Path : `artifacts/phase-09-02b/backup-pre-parser-fix-20260601T115012Z.sql`
- Size : **1,403,563 bytes** (~1.4 MB)
- Source : `python scripts/backup_db.py --phase phase-09-02b --reason parser-fix`
- Coverage : full `pg_dump` of the `ede` database (all schemas, all tables).

## 2. Pre-update snapshot

`SELECT COUNT(*) AS verified_cash FROM deals WHERE juridiction='FR' AND offer_price_quality_flag='verified_cash';`

| verified_cash |
|---:|
| 596 |

Sample of 5 deals to be corrected:

| Ref | Target | offer_price (pre) |
|---|---|---:|
| 218C1907 | SERMA GROUP | 229.190000 |
| 219C2667 | OENEO | 2.720000 |
| 223C2035 | TECHNICOLOR CREATIVE STUDIOS | 0.010000 |
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.340000 |
| 224C1143 | ADEUNIS | 0.175000 |

## 3. Update execution

Driver : `scripts/p92_02b_apply_corrections.py --apply`

Source of truth : `data/audits/p92_02b_re_run_comparison.csv` rows
filtered on `category = 'CORRECTED'` (64 rows).

Safeguards:

1. Bails out if `artifacts/phase-09-02b/backup-pre-parser-fix-*.sql`
   does not exist (forces backup discipline).
2. Per-row defensive guard : the script re-reads `offer_price_quality_flag`
   AND `offer_price` from the DB at execution time and skips any row
   where the flag drifted away from `verified_cash` or the current price
   no longer matches the CSV's `old_offer_price` (would mean a parallel
   writer touched the row since Step 1h).
3. All 64 UPDATEs wrapped in a single `AsyncSession` transaction. Any
   exception triggers a full rollback (no partial state).

Dry-run output (no commit):

```
[STEP-1i] backup: backup-pre-parser-fix-20260601T115012Z.sql (1,403,563 bytes)
[STEP-1i] 64 CORRECTED rows to apply
[STEP-1i] mode: DRY-RUN (no commit)
[STEP-1i] DRY-RUN — rolled back, no DB write

applied            : 64
skipped (drift)    : 0
failed             : 0
```

Apply output:

```
[STEP-1i] backup: backup-pre-parser-fix-20260601T115012Z.sql (1,403,563 bytes)
[STEP-1i] 64 CORRECTED rows to apply
[STEP-1i] mode: APPLY (transactional)
[STEP-1i] COMMITTED — 64 rows updated

applied            : 64
skipped (drift)    : 0
failed             : 0
```

## 4. Post-update verification

```sql
SELECT COUNT(*) AS verified_cash_count,
       COUNT(*) FILTER (WHERE offer_price IS NOT NULL) AS with_price
FROM deals
WHERE juridiction='FR' AND offer_price_quality_flag='verified_cash';
```

| verified_cash_count | with_price |
|---:|---:|
| 596 | 596 |

Row count unchanged (596 → 596), no nulls introduced.

Same 5-deal spot-check, post-update:

| Ref | Target | pre | post | Δ |
|---|---|---:|---:|---|
| 218C1907 | SERMA GROUP | 229.19 | **235.000000** | +2.5% |
| 219C2667 | OENEO | 2.72 | **13.500000** | +396% |
| 223C2035 | TECHNICOLOR CREATIVE STUDIOS | 0.01 | **1.630000** | +16200% |
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | **2.850000** | +22% |
| 224C1143 | ADEUNIS | 0.175 | **0.450000** | +157% |

All 5 corrections match the values reported by Step 1h
(`docs/phase-09/p92_02b_re_run_audit.md`).

## 5. Audit log

Per-row record at `data/audits/p92_02b_db_update_log.csv` (gitignored).
Columns:

- `deal_id`, `regulator_ref`, `target_name`
- `old_offer_price`, `new_offer_price`, `new_source`
- `update_timestamp` (UTC ISO 8601)
- `sql_status` — one of `applied`, `skipped_invalid_new_price`,
  `skipped_missing_deal`, `skipped_flag_drift`, `skipped_price_drift`

Distribution on this run:

| sql_status | Count |
|---|---:|
| `applied` | 64 |
| skipped (any kind) | 0 |
| failed | 0 |

## 6. Rollback procedure

If a downstream regression points the finger at this update:

1. **Stop the BDIF poller** (cron job + any manual ingest) to prevent
   new writes against the rolled-back state.
2. **Restore the backup** :
   ```
   docker exec -i ede-postgres psql -U ede -d ede < artifacts/phase-09-02b/backup-pre-parser-fix-20260601T115012Z.sql
   ```
   The dump is a full `pg_dump` — restore replays every row exactly as
   it was at 2026-06-01 11:50 UTC.
3. **Verify** :
   ```sql
   SELECT regulator_ref, target_name, offer_price FROM deals
   WHERE regulator_ref IN ('219C2667','224C1143','223C2035')
   ORDER BY regulator_ref;
   ```
   Expected post-restore: OENEO 2.72, ADEUNIS 0.175, TECHNICOLOR 0.01.
4. **Revert this commit** on the branch and re-open the audit.

## 7. Next step

- **Step 1j** : re-train the Phase 6 scoring model (`scoring V1.1`) on
  the cleaned dataset. Expect minor AUC / Brier shifts since 64 deals
  out of 596 now carry a different `offer_price` feature value (and
  derived features like `offer_premium`, `expected_return`).

The Step 1i write is independent of Step 1j — if scoring re-train
surfaces a problem, the rollback procedure above brings the prices back
without unwinding any model artefact.
