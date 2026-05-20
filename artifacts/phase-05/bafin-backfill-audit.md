# Phase 5 — Step 9 BaFin Live Backfill Audit

**Date:** 2026-05-19
**Branch:** `phase-05-bafin-poller` (not yet pushed — awaiting user VALIDATE)
**Script:** `python scripts/bafin_run_once.py 365`
**ScrapingBee key:** NOT used — BaFin direct httpx works (Step-0 finding)

---

## TL;DR

| Criterion | Target | Actual | Pass |
|---|---|---|---|
| Angebotsunterlagen DE discovered (12-month window) | ≥10 | **16** | ✅ |
| PDFs downloaded & validated | ≥5 | **16** (0 failed) | ✅ |
| Known-deal manual validation | ≥1 | **3** validated (1&1, CompuGroup, JD/CECONOMY) | ✅ |
| AMF regression | FR=60 + 60 filing_amf | **FR=60 + 60 filing_amf** | ✅ |
| Consob regression | IT=22 + 22 filing_consob | **IT=22 + 22 filing_consob** | ✅ |
| ScrapingBee credits consumed | 0 | **0** new (2 carried over from Phase 4) | ✅ |
| CI + coverage | green ≥80 % | **200 passed locally, 90 % coverage** | ✅ |

---

## Run summary (artifact: `bafin-backfill.json`)

```
discovered:        16
created:           16  (0 skipped, 0 duplicates)
pdf_downloaded:    16  (0 failed)
since cutoff:      2025-05-19  (365 days back from 2026-05-19)
duration:        18.61 s
stop reason:    natural end of listing (no row older than `since` reached)
```

---

## DB state (post-Phase 5 backfill)

```
juridiction | deals | filing events
FR          |    60 | 60 (filing_amf)    — Phase 3 baseline intact
IT          |    22 | 22 (filing_consob) — Phase 4 baseline intact
DE          |    16 | 16 (filing_bafin)  — NEW
```

`alembic_version` = **0007** (migration `ALTER TYPE deal_type_enum ADD VALUE`
applied cleanly against the live DB without disturbing existing rows).

---

## DE deals (newest first, 16 rows)

| # | regulator_ref | Target (Zielgesellschaft) | Acquirer (Bieter) | type | date | PDF |
|---|---|---|---|---|---|---|
| 348 | BAFIN-DE000CBK1001-20260505 | COMMERZBANK Aktiengesellschaft | UniCredit S.p.A | opa_volontaire_totalitaria | 2026-05-05 | ✓ |
| 349 | BAFIN-DE000KC01000-20260205 | Klöckner & Co SE | Worthington Steel GmbH | opa_volontaire_totalitaria | 2026-02-05 | ✓ |
| 350 | BAFIN-DE000A0Z1JH9-20251117 | PSI Software SE | Zest Bidco GmbH | opa_volontaire_totalitaria | 2025-11-17 | ✓ |
| 351 | BAFIN-DE0007504508-20251021 | Turbon AG | S77 Holdings GmbH | opa_obligatoire | 2025-10-21 | ✓ |
| 352 | BAFIN-DE000A1E89S5-20251002 | Readcrest Capital AG | Obotritia Capital KGaA | opa_volontaire_totalitaria | 2025-10-02 | ✓ |
| **353** | **BAFIN-DE0007257503-20250901** | **CECONOMY AG** | **JINGDONG HOLDING GERMANY GMBH** | **opa_volontaire_totalitaria** | **2025-09-01** | **✓ (known deal #3 — JD.com)** |
| 354 | BAFIN-DE000A254294-20250804 | Heidelberger Beteiligungsholding AG | Apeiron Investment Group Ltd | opa_obligatoire | 2025-08-04 | ✓ |
| 355 | BAFIN-DE000FPH9000-20250731 | Francotyp-Postalia Holding AG | SALTARAX GmbH | opa_volontaire_parziale | 2025-07-31 | ✓ |
| 356 | BAFIN-DE0005490601-20250725 | Leo International Precision Health AG | SCGI Corporate Finance GmbH | opa_obligatoire | 2025-07-25 | ✓ |
| 357 | BAFIN-DE000A2P4LJ5-20250714 | PharmaSGP Holding SE | FUTRUE GmbH | delisting_offer | 2025-07-14 | ✓ |
| 358 | BAFIN-DE000FPH9000-20250709 | Francotyp-Postalia Holding AG | Francotyp-Postalia Holding AG | delisting_offer | 2025-07-09 | ✓ |
| 359 | BAFIN-DE000A1K0375-20250708 | artnet AG | Leonardo Art Holdings GmbH | delisting_offer | 2025-07-08 | ✓ |
| 360 | BAFIN-DE000A2E4T77-20250630 | H&R GmbH & Co. KGaA | H&R Holding GmbH | opa_volontaire_parziale | 2025-06-30 | ✓ |
| **361** | **BAFIN-DE0005545503-20250605** | **1&1 AG** | **United Internet AG** | **opa_volontaire_parziale** | **2025-06-05** | **✓ (known deal #1 — United Internet take-private)** |
| 362 | BAFIN-DE000PSM7770-20250604 | ProSiebenSat.1 Media SE | PPF IM LTD | opa_volontaire_parziale | 2025-06-04 | ✓ |
| **363** | **BAFIN-DE000A288904-20250523** | **CompuGroup Medical SE & Co . KGaA** | **Caesar BidCo GmbH** | **delisting_offer** | **2025-05-23** | **✓ (known deal #2 — CVC delisting)** |

### Deal-type distribution

| Canonical type | Count |
|---|---|
| `opa_volontaire_totalitaria` (Übernahmeangebot) | 5 |
| `opa_volontaire_parziale` (Erwerbsangebot/Teilerwerbsangebot) | 4 |
| `delisting_offer` (Delisting variants) | 4 |
| `opa_obligatoire` (Pflichtangebot) | 3 |

**Migration 0007 working as designed** — the 4 delisting deals all land in `delisting_offer` (previously had no canonical value).

---

## Known-deal manual validation

Per Step-0 brief the canonical targets were Covestro/ADNOC, MorphoSys/Novartis, and a recent take-private of operator's choice. The first two fall outside the 365-day window:

| Target deal | Status |
|---|---|
| Covestro / ADNOC (XRG) | Angebotsunterlage published 2024-Q4 → outside window |
| MorphoSys / Novartis | 2024 → outside window |

Three deals **within the window** that are independently verifiable in financial press:

| # | Deal | DB id | Notes |
|---|---|---|---|
| 1 | **1&1 AG → United Internet** | 361 | United Internet (majority owner, ~80 %) launches a `Teilerwerbsangebot` / partial offer on the minority float. Mapped to `opa_volontaire_parziale`. ISIN `DE0005545503`, announced 2025-06-05. **Field accuracy: target + acquirer + type all correct.** |
| 2 | **CompuGroup Medical → Caesar BidCo (CVC)** | 363 | CVC Capital Partners acquires CompuGroup Medical and delists it. Mapped to `delisting_offer` (Delisting-Übernahmeangebot variant). ISIN `DE000A288904`, announced 2025-05-23. **Field accuracy: correct, delisting nuance preserved.** |
| 3 | **CECONOMY → JD.com** | 353 | JD.com (via JINGDONG HOLDING GERMANY GMBH) launches a takeover offer for CECONOMY (parent of MediaMarkt/Saturn). Mapped to `opa_volontaire_totalitaria` (Übernahmeangebot). ISIN `DE0007257503`, announced 2025-09-01. **Field accuracy: correct.** |

All three pass the manual validation criterion.

---

## ScrapingBee budget

| Item | Value |
|---|---|
| Credits consumed by Phase-5 backfill | **0** |
| `vendor_api_usage` table | 2 rows (carried over from Phase-4 Consob backfill) |
| Monthly cap | 900 |
| Remaining this month | 898 |

Direct httpx confirmed: listing (1 GET, free) + 16 PDFs (16 GETs, free, all real `%PDF-` magic, sizes 0.7-3.3 MB). Same UA + `Accept-Language: de-DE` headers from Step-0 spec.

---

## CI / coverage (local pre-push)

```
200 passed in 63.72s
TOTAL coverage 90% (1872/2082 statements, 332/400 branches)
```

Per-module bafin coverage:
- `discovery.py` — 90 %
- `fetcher.py` — 90 %
- `parser.py` — 86 %
- `poller.py` — 83 %
- `service.py` — 97 %

All ≥ 80 % per success criterion.

---

## Files written this round (post-commit)

```
alembic/versions/20260519_1600_0007_deal_type_cross_jurisdiction_extensions.py
docs/research/bafin-source-mapping.md
src/core/enums.py                          (+ 2 enum values)
src/core/scrapingbee_client.py             (moved from src/ingestion/consob/)
src/ingestion/bafin/{__init__,discovery,fetcher,parser,service,poller}.py
src/ingestion/consob/__init__.py + 3 modules (import paths updated)
scripts/bafin_run_once.py
tests/fixtures/bafin/{angebotsunterlagen-listing.html, wrapper-commerzbank.html,
  sample_commerzbank_*.pdf, sample_kloeckner_*.pdf, sample_psi_software_*.pdf}
tests/ingestion/bafin/{__init__,test_discovery,test_fetcher,test_parser,
  test_service,test_poller}.py
tests/ingestion/consob/* (4 files — import path updates)
artifacts/phase-05/{step0_probe*.py, step0-probe*.json,
  bafin-backfill.json, bafin-backfill-stdout.txt, bafin-backfill-audit.md}
```

---

## Tech debt opened at phase 5 (to document in PR + DATA_SOURCES.md)

| # | Item | Severity | Owner |
|---|---|---|---|
| 1 | `Erwerbsangebot Änderung` (amendments) — currently ingested with parent's enum value but with no `parent_deal_id` column linking back to the original offer. Capture as `events.raw_payload.amendment_for=<slug>` in phase 5; structural fix (parent_deal_id column + UNIQUE-aware upsert) in phase 7. | low | phase 7 |
| 2 | `Untersagung` (regulatory prohibitions) — currently silently filtered at discovery. Future iteration could ingest as `event_type='regulatory_decision'` (would need new EVENT_TYPES enum value) for full audit trail. | low | phase 6-7 |
| 3 | `Erwerbsangebot Änderung` value `opa_volontaire_parziale` is a guess (default fallback). With only 1 row of this type in the 241-row archive, manual review is feasible — for now flagged in events.raw_payload.is_amendment. | very low | phase 7 |

---

## STOP — awaiting VALIDATE PHASE 5 before opening PR

Per Phase-5 brief:

> 9. STOP avant ouverture PR — attends VALIDATE final

Branch `phase-05-bafin-poller` has 2 commits locally:
- `26fc33f` — refactor scrapingbee_client → core + migration 0007
- `12b7827` — bafin ingestion pipeline + 49 tests

A 3rd commit (PR body draft + this audit + maybe a DATA_SOURCES.md update) is ready to be added once VALIDATE arrives.

**Local artifacts ready:** `artifacts/phase-05/{bafin-backfill.json, bafin-backfill-audit.md, bafin-backfill-stdout.txt}`.

ScrapingBee budget unchanged → no key-rotation action required this phase.
