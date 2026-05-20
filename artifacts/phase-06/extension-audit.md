# Phase 6 Step-0 Extension — 24-month backfill audit

**Date:** 2026-05-20
**Branch:** `phase-06-step0-extension-24mo` (not yet pushed)
**Backup:** `artifacts/phase-06/backup-pre-extension-24mo-20260520T124650Z.sql` (190 KB)

---

## TL;DR

| Metric | Before (Phase 5) | After (Phase 6 Step-0 ext) | Delta |
|---|---:|---:|---:|
| Total deals | 98 | **819** | +721 |
| FR (AMF BDIF) | 60 | 730 | +670 |
| IT (Consob) | 22 | 47 | +25 |
| DE (BaFin) | 16 | 42 | +26 |
| Total events | 98 | 819 | +721 |
| ScrapingBee credits used | 0 | 2 | +2 (Consob, 2 listing pages) |
| Alembic version | 0007 | **0008** | migration 0008 applied |

**Total time:** ~15 min (12 min BDIF + 55 s Consob + 35 s BaFin + DB ops).
**Total ScrapingBee budget:** 2 / 900 (898 remaining, well under the 100-credit hard ceiling).

---

## Success criteria evaluation

| # | Criterion | Target | Actual | Status |
|---|---|---|---|---|
| 1 | At least 200 deals total | ≥200 | **819** | ✅ |
| 2 | ≥5 failures identifiable | ≥5 | **0** (Untersagung) + manual TBD (FR/IT) | ⚠️ partial |
| 3 | Multi-stage deals enriched | yes | yes (top targets carry 6-9 filings each) | ✅ |
| 4 | AMF + IT + DE pipelines, no regression | green | green | ✅ |
| 5 | ScrapingBee credits ≤100 | ≤100 | 2 | ✅ |
| 6 | Test coverage ≥80 % | ≥80 % | 27 bafin tests pass (full suite TBD pre-PR) | ⏳ |

### ⚠️ Criterion #2 — failure detection: 0 Untersagung captured

The brief expected Untersagung (BaFin §15 WpÜG prohibitions) to provide the label=0 backbone. Discovery code + migration 0008 are in place and ingest Untersagung correctly when they appear, **but the 9 Untersagung rows in the captured BaFin fixture all cluster in 2017–2018–2019** — too old for the `since=2024-05-20` cutoff. The 24-month window happens to cover an era where BaFin issued no prohibitions.

**Three options to surface 5+ failures for the training set:**

| Option | What | Cost | Pros / Cons |
|---|---|---|---|
| **A** | Re-run BaFin with `days_back=2920` (~8 years) | 0 ScrapingBee, ~5 min | Cleanest. Pulls historical Untersagung (likely 5-9) + adds ~150 historical DE deals. Recommended. |
| **B** | Manually identify FR/IT failures during labelling | 0 cost, +1 h labelling | Relies on news search per deal. Slower, requires operator domain knowledge. |
| **C** | Add automated `withdrawal` detection via "visa without follow-on filing within 180 j" heuristic on FR BDIF chains | medium dev | Phase-7 feature, not Phase-6 critical path. |

**Recommendation:** Option A. Run `python scripts/bafin_run_once.py 2920` once after this PR merges. Free, fast, surfaces historical Untersagung + further enriches the DE training set.

---

## Per-jurisdiction details

### FR — BDIF (60 → 730, +670)

| Field | Value |
|---|---|
| Script arg passed | `730` (legacy positional = `max_items`, not days) |
| Actual date range walked | **2022-01-11 → 2026-05-19** (~4 years, not 24 mo) |
| HTTP calls | 684, all 200 |
| ScrapingBee credits | 0 (BDIF is a public API) |
| `deal_type` distribution | `opa_simplifiee` 369 · `opa` 142 · `opr` 139 · `opra` 37 · `opr_ro` 33 · `ope` 10 |
| Multi-stage targets | 1000MERCIS=9, IDSUD=9, ALTUR=8, ADVENIS=7, NHOA=7, MEDIA 6=7, TESSI=7, SPIR=7, IGE+XAO=6 |

**Important nuance:** BDIF returns each filing stage as a separate row (visa → réouverture → suite → OPR-RO chain). 730 rows ≠ 730 unique OPAs. Estimated unique OPAs in the 730 rows: ~150–200. The labelling tool will need to **collapse multi-stage chains by `(target_name, juridiction)` with a date-gap heuristic** to produce one label per underlying deal. This is fine — the chain itself carries the training signal (chain length, terminal stage type, gap distribution).

BDIF tech debt: the poller has no `since=` filter (uses `max_items` hard cap). Walking 24 mo precisely would need either (a) an API date filter (TBD whether BDIF exposes one) or (b) client-side date stop. Current 730-item run overshoots by ~2 years. Not blocking — labelling can filter by date after import.

### IT — Consob (22 → 47, +25)

| Field | Value |
|---|---|
| Script arg passed | `730` (days_back, refactored in this branch) |
| Actual date range walked | 2024-05-27 → 2026-05-11 (window respected via `since=2024-05-20`) |
| Listing pages fetched | 2 |
| ScrapingBee credits | 2 |
| Duration | 55.09 s |
| Stop reason | `consob.discovery.stop_on_since` (page 2 all older than 2024-05-20) |
| Discovered / created / skipped | 47 / 25 / 22 (22 already in DB from Phase 4) |
| PDFs downloaded | 47 (0 failed) |
| `deal_type` distribution | `opa_volontaire_totalitaria` 21 · `opa_obligatoire` 15 · `opas` 7 · `opa_volontaire_parziale` 4 |

### DE — BaFin (16 → 42, +26)

| Field | Value |
|---|---|
| Script arg passed | `730` (days_back, supported since Phase 5) |
| Actual date range walked | 2024-06-14 → 2026-05-05 (window respected) |
| ScrapingBee credits | 0 (direct httpx confirmed in Phase 5) |
| Duration | 34.75 s |
| Discovered / created / skipped | 42 / 26 / 16 (16 already in DB from Phase 5) |
| PDFs downloaded | 42 (0 failed) |
| `deal_type` distribution | `delisting_offer` 19 · `opa_volontaire_totalitaria` 14 · `opa_obligatoire` 5 · `opa_volontaire_parziale` 4 · `prohibition_ungenutzt` **0** |
| Notable 2024-vintage adds | MorphoSys AG (id 1083, delisting 2024-07-04), SYNLAB AG (id 1084, delisting 2024-06-14), New Work SE (id 1082, delisting 2024-07-15) |

---

## Code changes shipped (3 atomic commits ready to make)

1. **Migration 0008** — `ALTER TYPE deal_type_enum ADD VALUE IF NOT EXISTS 'prohibition_ungenutzt'` (autocommit_block + idempotent).
2. **BaFin discovery refactor** — remove `Untersagung` filter, add classifier rule mapping to `prohibition_ungenutzt`. Tests updated (`test_parse_listing_ingests_untersagung_as_prohibition`, classifier parametrize adds `Untersagung → prohibition_ungenutzt`, replace `returns_none_on_untersagung` with `returns_none_on_unknown_narrative`).
3. **`consob_run_once.py`** — refactor positional arg from `max_pages` to `days_back`. Internal `_MAX_PAGES_SAFETY_CAP=30`. Passes `since=today-days_back` to `run_backfill`.

`src/core/enums.py` extends `DealType` Literal + `DEAL_TYPES` tuple with `prohibition_ungenutzt`.

---

## STOP — awaiting VALIDATE before CSV re-export

Per brief: **"STOP après l'audit DB. Attends VALIDATE utilisateur avant export CSV final."**

Two questions for the operator:

1. **Re-run BaFin with `days_back=2920` (8 years)** to surface historical Untersagung as automated label-0 source? (Free, ~5 min, addresses criterion #2.)
2. **CSV re-export scope**: dump all 819 rows for labelling, or filter to a subset (e.g., last 24 mo only, or collapse FR multi-stage chains to one row per target+visa-date)?

Once decisions arrive, I'll:
- (optional) Run the 8-year BaFin extension
- `scripts/export_deals_for_labelling.py --output artifacts/phase-06/deals_to_label_24mo.csv`
- `scripts/enrich_labelling_csv.py` → `deals_to_label_24mo_v2.csv`
- Commit branch (3 atomic commits) and stop before PR per Phase-6 protocol
