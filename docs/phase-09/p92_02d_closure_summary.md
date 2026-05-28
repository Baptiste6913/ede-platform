# Phase 9.2 02d — closure summary (Consob flag promotion)

Closes the P9.2 02d sprint (low-risk layup, mirror of P9.1a BaFin
flag promotion on the IT corpus). Step 0 audit + decision pass +
script + tests + apply + score invalidation. Branch
`phase-09-02d-consob-promote-flags` ready for PR.

## 1. Scope delivered

### Categorization & promotion script (`scripts/promote_consob_flags_02d.py`)

First-match rule on 47 IT deals:
1. **OUTLIER** → `failed_validation` (non-NULL price ∉ `[0.01, 10 000]`)
2. **MIXED** → `suspect_mixed` (deal_type = `opas`)
3. **MANUAL_REVIEW** → `manual_review` (NULL price OR `target_name = '[pending parse]'`)
4. **PROMOTABLE** → `verified_cash` (else); annotates `statistical_outlier=True`
   when `price > p95 × 3 = 107.19 €` (audit-trail only, doesn't block
   promotion)

`parser_version` bumped to 2 on every re-categorized row.
Transactional per deal, idempotent (second run = 47 noop).

Dry-run by default; `--apply` triggers UPDATEs.

### Test coverage (`tests/ingestion/consob/test_consob_promotion_02d.py`)

11 unit cases on the pure `categorize()` function:
- `test_promotable_cash_in_bounds` — happy path verified_cash
- `test_health_italia_high_price_promoted_with_outlier_flag` —
  300 € PROMOTABLE + `statistical_outlier=True`
- `test_null_price_handled_no_typeerror` — defends the non-NULL
  guard on OUTLIER (prevents `None < Decimal` TypeError regression)
- `test_pending_parse_to_manual_review` — `[pending parse]` marker
- `test_banco_bpm_outlier` — opa_* + 3.8 B → failed_validation
- `test_below_lower_bound_rejected` — 0.005 fence-post
- `test_opas_routed_to_mixed` — happy path suspect_mixed
- `test_opas_priority_over_bounds` — OPAS 5 € → suspect_mixed
- `test_opas_with_null_price_to_mixed_not_manual_review` —
  Mediobanca / Sondrio NULL+opas
- `test_banco_bpm_opas_outlier_to_failed_not_mixed` — defends
  OUTLIER-before-MIXED ordering against regression
- `test_outlier_threshold_exact_boundary` — fence-post on 107.19

## 2. Decompte final (35 / 5 / 6 / 1 = 47 ✓)

| Category | Flag | Count | Composition |
|---|---|---|---|
| PROMOTABLE | `verified_cash` | **35** | 34 normal + 1 statistical_outlier=True (Health Italia 300 €) |
| MIXED | `suspect_mixed` | 6 | 4 priced opas (Illimity, Banca Sistema×2, Unieuro) + 2 OPS-prefixed NULL (Mediobanca-montepaschi, Banca Pop Sondrio) |
| MANUAL_REVIEW | `manual_review` | 5 | 3 NULL extraction (Piovan, morif, Comal) + 2 partial ingestion (CIR 2026, Antares — `[pending parse]` target_name) |
| OUTLIER | `failed_validation` | 1 | Banco BPM 3.828 B €/share (controvalore complessivo mis-parsed) |
| **Total** | | **47 / 47** ✓ | |

Post-apply DB verification:

```
 offer_price_quality_flag | parser_version | count
--------------------------+----------------+-------
 verified_cash            |              2 |    35
 suspect_mixed            |              2 |     6
 manual_review            |              2 |     5
 failed_validation        |              2 |     1
```

## 3. Décisions actées (post Step 0)

1. **Banco BPM (3.828 B €)** → `failed_validation` (OUTLIER prime
   sur MIXED). Le sample code du brief avait l'ordre MIXED → OUTLIER
   qui aurait routé Banco BPM en `suspect_mixed` ; corrigé en
   OUTLIER → MIXED (avec guard non-NULL pour éviter le TypeError
   sur Mediobanca / Sondrio NULL+opas).
2. **Health Italia (300 €)** → `verified_cash` + `statistical_outlier=True`
   audit trail. Gate p95 × 3 = 107.19 €, seul hit dans le corpus.
3. **`[pending parse]` target_names (CIR 2026 id 327, Antares id 333)** →
   `manual_review`. Si le target_name parse a échoué, l'intégrité du
   price parsing sur le même PDF n'est pas garantie ; re-ingestion
   requise avant promotion.
4. **OPS-prefixed opas-typed (Mediobanca id 342, Banca Pop Sondrio
   id 344)** → `suspect_mixed` en 02d. Reclassification en
   `share_swap_pure` (avec migration enum) = scope 02e.
5. **No migration en 02d** — les 4 flags cibles existent déjà dans
   `OFFER_PRICE_QUALITY_FLAGS` + CHECK constraint (migration 0015).

## 4. Score invalidation

Tous les 47 deals IT ont changé de flag (de `suspect_low_unverified`
par défaut vers leur flag final). Les scores existants sont
invalidés en bloc :

```sql
DELETE FROM scores WHERE deal_id IN (SELECT id FROM deals WHERE juridiction='IT')
-- 43 rows deleted
```

Phase 6 re-scorera les 35 nouveaux `verified_cash` IT candidates au
prochain run du scoring pipeline (cohérent avec l'approche P9.1c).
Les 6 `suspect_mixed` + 5 `manual_review` + 1 `failed_validation`
restent hors du flow de scoring (filtre Phase-8 `load_candidates`).

## 5. Mesured impact

### Phase 8 trading flow

**+35 candidates `verified_cash`** désormais éligibles au scoring +
trading pipeline IT (était : 0 / 47 IT trades exposed post-P9.1c).
Combinés aux 32 BaFin `verified_cash` + 1 BaFin `verified_mixed` de
P9.1c, le pool éligible passe de **33 → 68 candidates trans-
jurisdictionnels** (FR reste 0 / 730 jusqu'à 02a).

### Quality flags hygiene

- 0 `suspect_low_unverified` résiduel sur IT (était : 47 / 47).
- 47 / 47 IT à `parser_version = 2`.
- Score table propre, prête pour re-scoring Phase 6.

## 6. Dette résiduelle (open work for 02e / 02f / next branches)

### `phase-09-02e-consob-opas-mixed` (next, 1-2 jours)

- **Goal** : structuration des 6 `suspect_mixed` deals via le
  schema P9.1c `deal_consideration` (cash leg + share ratio +
  acquirer).
- **Cas** :
  - Banca Sistema OPAS (id 335 + id 326) : cash `1,382` + share
    `21:1 Kruso Kapital` — direct mirror du pattern P9.1c.
  - Illimity (id 347), Unieuro (id 1050) : OPAS standard à
    structurer.
  - **Reclassification OPS-prefixed** (id 342 Mediobanca, id 344
    Banca Pop Sondrio) : ajout d'un nouvel enum value
    `share_swap_pure` (migration nécessaire) et reroute de ces 2
    deals depuis `suspect_mixed`.
- **Acceptance** : `deal_consideration` populée pour 4 OPAS
  in-bounds, 2 OPS-prefixed reclassifiées, 0 `suspect_mixed`
  résiduel en IT.

### `phase-09-02a-amf-wire-parser` (next-next)

- Wire `extract_pdf_metadata` dans `src/ingestion/amf/service.py`
  (cf. smoking gun service.py:217-218 dans p92_db_audit_synthesis.md).
- Backfill script sur les 730 deals FR historiques.
- Inclut le fix `\xa0` literal bug atomique (`parser.py:66` + `:278`).
- **Acceptance** : 0 → ~450 / 730 FR avec `offer_price` extrait.

### Re-ingestion needed (small)

- 2 deals avec `target_name = '[pending parse]'` (CIR 2026 id 327,
  Antares id 333). Re-parser le `target_name` depuis le PDF body,
  puis re-run 02d (ils passeront alors en PROMOTABLE).

### Conditional (02f gating)

- 3 deals NULL extraction (Piovan id 1039 — font encoding cassé ;
  Monti Riffeser id 1035 ; Comal id 1040). Couverts par OCR
  fallback en 02f **seulement si** la long tail joint FR + IT
  dépasse 5 % post-02a/02b/02d. Sinon dette P10.

### Smaller items

- **Banco BPM controvalore-vs-unit_price parser bug** : isolé en
  `failed_validation` pour ne pas polluer 02e ; investigation
  parser deferred à P10 ou si récurrence sur d'autres OPAS.
- Considérer `pdf_text_extraction_failed` flag (nouveau enum value)
  pour les Piovan-class deals — alternative semantically plus
  propre que `manual_review`. P10 housekeeping si pertinent.

## 7. Artifact inventory

### Code

- `scripts/promote_consob_flags_02d.py` (~165 lignes, dataclass
  `DealView` + fonction pure `categorize()` + async `_promote()`
  + CLI `--apply`)
- `tests/ingestion/consob/test_consob_promotion_02d.py` (11 cases,
  0.9 s à exécuter)

### Docs

- `docs/phase-09/p92_02d_categorization.md` (47-row table)
- `docs/phase-09/p92_02d_step0_synthesis.md` (Step 0 + décisions)
- `docs/phase-09/p92_02d_closure_summary.md` (ce fichier)

### Audits (gitignored sous `data/audits/`)

- `p92_02d_consob_full.csv` — snapshot des 47 deals pre-promotion
- `p92_02d_promotion_results.csv` — résultat dry-run + apply
  (47 lignes : deal_id, target_name, regulator_ref, offer_price,
  deal_type, old_flag, new_flag, statistical_outlier, action)

### Schema

Aucune migration. Tous les flags cibles préexistent dans
`OFFER_PRICE_QUALITY_FLAGS` enum + CHECK constraint migration 0015.

## 8. Next step — PR + merge

Operator merge per the [G] convention from P9.1c. Branch
`phase-09-02d-consob-promote-flags` ready for review. CI must be
green (lint + mypy + tests) before merge. PR body draft staged at
`.git/pr_body_draft_02d.md`.
