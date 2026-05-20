# Candidate failures from the 24-month extension dataset

**Date:** 2026-05-20
**Dataset:** ede DB after Phase-6 Step-0 extension (FR=730 / IT=47 / DE=42 = 819 deals, `since=2024-05-20`)

Run as part of Decision #3 (Phase-6 Step-0 extension validation): surface deals that look like failures/withdrawals so the labelling effort can pre-fill `candidate_failure_flag` in the final CSV.

---

## Q1 — FR isolated visas (>180 j without follow-on filing)

### Q1 as written in the brief

```sql
SELECT d.regulator_ref, d.target_name, d.announcement_date,
       (CURRENT_DATE - d.announcement_date::date) AS days_since_visa,
       (SELECT count(*) FROM events e WHERE e.deal_id = d.id) AS events_count
FROM deals d
WHERE d.juridiction = 'FR'
  AND d.announcement_date >= '2024-05-20'
  AND (CURRENT_DATE - d.announcement_date::date) > 180
  AND (SELECT count(*) FROM events e WHERE e.deal_id = d.id) <= 1
ORDER BY days_since_visa DESC;
```

**Result: 129 rows** — but the `events_count <= 1` predicate matches every FR row in the DB. The ingestion service creates exactly **one** `filing_amf` event per `deals` row at upsert time (see `src/ingestion/amf/service.py`); there is no follow-on event source connecting filings of the same target. So the literal query reduces to "every FR deal >180 j old". Not actionable as a failure shortlist.

### Q1 corrected (intended semantics)

Group by target across BDIF filings — "targets that appear only once in 24 mo and that one filing is >180 j old":

```sql
SELECT target_name,
       MIN(regulator_ref) AS first_ref,
       MIN(announcement_date) AS first_visa,
       CURRENT_DATE - MIN(announcement_date::date) AS days_since_first_visa,
       COUNT(*) AS bdif_filings
FROM deals
WHERE juridiction = 'FR'
  AND announcement_date >= '2024-05-20'
  AND target_name <> '[pending parse]'
GROUP BY target_name
HAVING COUNT(*) = 1
   AND (CURRENT_DATE - MIN(announcement_date::date)) > 180
ORDER BY days_since_first_visa DESC;
```

**Result: 9 strong candidates.** These targets show 1 BDIF filing in 24 mo + >180 j old with no follow-on visa = likely abandoned/withdrawn:

| Target | First ref | First visa | Days since | BDIF filings |
|---|---|---|---:|---:|
| COVIVIO HOTELS | 224C0763 | 2024-05-31 | 719 | 1 |
| AUREA | 219C1696 | 2024-08-29 | 629 | 1 |
| FUTUREN | 219C2562 | 2024-09-25 | 602 | 1 |
| LE BELIER | 220C4606 | 2024-09-25 | 602 | 1 |
| ETABLISSEMENTS FAUVET GIREL | 221C3400 | 2024-09-26 | 601 | 1 |
| UNION FINANCIERE DE FRANCE BANQUE | 223C0159 | 2024-09-26 | 601 | 1 |
| SOMFY SA | 222C2728 | 2024-09-26 | 601 | 1 |
| ZODIAC AEROSPACE | 217C2859 | 2024-10-15 | 582 | 1 |
| LISI | 223C0548 | 2024-12-04 | 532 | 1 |

These 9 will be pre-flagged `candidate_failure_flag=Y` in the collapsed CSV.

⚠️ False-positive risk: some of these might be **simplified single-stage closures** (notably for tiny floats where the entire process is one filing). Manual verification on AMF news still required. Realistic split: ~5-6 true failures, 3-4 single-stage closures.

---

## Q2 — IT candidate withdrawals (UC/BPM + expected_close passed)

### Q2 as written

```sql
WHERE (acquirer_name ILIKE '%unicredit%' AND target_name ILIKE '%banco bpm%')
   OR expected_close_date < CURRENT_DATE - INTERVAL '60 days'
```

**Result: 41 rows** — over-broad because the `expected_close_date` predicate matches every IT deal whose listed acceptance period is in the past (which is most of them; the IT acceptance period is ~30 j by law). And the UC/BPM combo did **not** match because the discovery extractor produced `acquirer_name='[pending parse]'` on the offer row — the SQL ILIKE on `acquirer_name` returns 0 hits.

The UC/BPM withdrawal is in the DB but not flagged by this literal query. See "Manual UC/BPM lookup" below.

### Strongest signal IT candidates (oldest expected_close past + recognizable names)

Top 12 by days past expected close — these are deals where the formal acceptance period ended >500 j ago. For most, the operation is closed by now; for the ~10-15 % that aren't tracked downstream by Consob, this is the failure cohort.

| regulator_ref | Target | Acquirer | Announce | Expected close | Days past | Note |
|---|---|---|---|---|---:|---|
| CONSOB-opa_saes_20240527 | SAES Getters Spa | SGG Holding Spa | 2024-05-27 | 2024-06-21 | 698 | Settlement Q3 2024 — likely 1 |
| CONSOB-opa_openjobmetis_20240610 | Plavisgas Srl | Openjobmetis Spa | 2024-06-10 | 2024-06-28 | 691 | Reverse offer — unusual, verify |
| CONSOB-opa_Civitanavi_Systems_20240527 | Civitanavi Systems Spa | Honeywell II Srl | 2024-05-27 | 2024-07-19 | 670 | Honeywell take-private — likely 1 |
| CONSOB-opa_medica_20240701 | Medica Spa | MavenDanc Srl | 2024-07-01 | 2024-07-19 | 670 | |
| CONSOB-opa_vianini_20240708 | Capitolium Srl | Vianini Spa | 2024-07-08 | 2024-07-26 | 663 | Reverse offer |
| CONSOB-opa_saras_20240712 | Saras spa | Varas Spa | 2024-07-12 | 2024-08-09 | 649 | Vitol/Trafigura JV — likely 1 |
| CONSOB-opa_greenthesis_20240819 | Eagle Spa | Greenthesis Spa | 2024-08-19 | 2024-09-12 | 615 | |
| CONSOB-opa_retex_20240819 | Alkemy Spa | Retex Spa | 2024-08-19 | 2024-09-20 | 607 | Alkemy was contested between Retex and Ksapa — withdrawal possible |
| CONSOB-opa_grey_20240909 | IVS Group Sa | Grey Sarl | 2024-09-09 | 2024-09-27 | 600 | Coca-Cola HBC family — likely 1 |
| CONSOB-opsc_unieuro_20240902 | Ruby Equity Investment Sàrl | Fnac-Darty Sa | 2024-09-02 | 2024-10-25 | 572 | Fnac-Darty / Unieuro — likely 1 |
| CONSOB-opa_anima_20250317 | Anima Holding Spa | Banco BPM Vita Spa | 2025-03-17 | 2025-04-04 | 411 | **Banco BPM successful tender on Anima — likely 1** |
| CONSOB-ops_Banco_BPM_20250428 | Banco BPM Spa | `[pending parse]` | 2025-04-28 | 2025-06-23 | 331 | **UC withdrew offer on Banco BPM 2025-07 — likely 0** (this is the canonical failure expected) |

### Manual UC/BPM lookup

The expected `(acquirer_name ILIKE '%unicredit%' AND target_name ILIKE '%banco bpm%')` predicate matched zero rows because the discovery extractor returned `[pending parse]` for the acquirer field on `CONSOB-ops_Banco_BPM_20250428`. The deal IS in the DB (id 1031, see Q2 row above with 331 days past). At labelling time:

```
id_cluster = 1031
regulator_ref = CONSOB-ops_Banco_BPM_20250428
target = Banco BPM Spa
acquirer = [pending parse]  ← UniCredit (verify via news)
label_y = 0
label_source = https://www.reuters.com/business/finance/unicredit-withdraws-banco-bpm-bid-2025-07-...
```

This will be **pre-flagged `candidate_failure_flag=Y` by name** in the collapse script (`target ILIKE '%banco bpm%' AND announcement_date >= 2025-04-01`).

---

## Q3 — DE 24-mo listing (visual scan, no automated failure filter)

42 rows = the full DE 24-mo dataset, ordered oldest first. The brief's intent is a hand-scan list, not an automated filter. **Zero `prohibition_ungenutzt`** in the window (all Untersagung rows in the fixture are 2017-2019, outside `since=2024-05-20`).

Highlights (chronological): SYNLAB AG (closed delisting Ephios 2024), MorphoSys AG (Novartis delisting 2024 — closed Q4 2024), Stemmer Imaging (Ventrifossa — closed; second filing 2024-11-29 = delisting follow-up), Covestro / ADNOC (FSR-cleared, closing pending H1 2026), CompuGroup / CVC (2024-12 then 2025-05 delisting variant — closed), Encavis / KKR (Elbe BidCo — closed), ABOUT YOU / Zalando (closed), METRO / EPGC (Křetínský — closed), Biotest / Grifols, ProSiebenSat.1 (two competing offers — MFE 2025-05 + PPF 2025-06; PPF withdrew, label MFE=1 PPF=0), 1&1 / United Internet, CompuGroup re-offer 2025-05, JD.com / CECONOMY, Klöckner & Co / Worthington Steel, **COMMERZBANK / UniCredit (announced 2026-05-05, ongoing)**.

**DE candidates for `label_y=0`:**
- BAFIN-DE000A2G9MZ9-20241129 (Stemmer Imaging delisting → duplicate of 2024-09 takeover — manual review)
- BAFIN-DE000PSM7770-20250604 (PPF on ProSiebenSat.1 — PPF withdrew Q3 2025 — **label 0**)

These DE candidates will be pre-flagged `candidate_failure_flag=Y` in the collapse script.

---

## Summary — automated pre-fills going into the collapsed CSV

| Pre-fill rule | Source | Approximate count |
|---|---|---|
| `candidate_failure_flag=Y` (FR) | 9 from corrected Q1 | 9 |
| `candidate_failure_flag=Y` (IT) | UC/BPM by name + 1 row near 600+ days past with known historical doubts | ~3 |
| `candidate_failure_flag=Y` (DE) | PPF/ProSieben + Stemmer duplicate | 2 |
| `label_y=1` auto (FR events_count >= 4) | Multi-stage chains | TBD by collapse run |
| `label_y` empty | Everything else | majority |

**Reasonable expectation post-labelling:** of ~280 collapsed rows, ~15-25 will end up as `label_y=0` (failures + lapsed offers). Sufficient training signal for the V1 logistic regression with class_weight='balanced'.
