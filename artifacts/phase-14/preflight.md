# Phase 14 — Step 0 preflight : pool frais FR+DE → décisions

Critère "frais / plausiblement ouvert" : `juridiction ∈ {FR,DE}` +
`announcement_date ≥ 2025-12-03` (6 mois) + `completion_label IS NULL`
(un label non-NULL = deal déjà clos historiquement → exclu) + `status='announced'`.

## Pool live exact = **17** (15 FR + 2 DE)

17 FR fraîches supplémentaires ont `completion_label` renseigné (déjà closes) →
**exclues**. Le pool live :

| Jur | ref | cible | annonce | type | offer | qflag | ticker_flag |
|---|---|---|---|---|---:|---|---|
| FR | 226C0694 | SOCIETE DE LA TOUR EIFFEL | 2026-05-19 | opr | — | suspect_low | (null) |
| FR | 226C0683 | POULAILLON | 2026-05-18 | opa_simplifiee | — | suspect_low | (null) |
| FR | 226C0644 | FNAC DARTY | 2026-05-12 | opa | 36.00 | verified_cash | (null) |
| DE | …CBK1001… | COMMERZBANK | 2026-05-05 | opa_vol_tot | — | verified_mixed | home_venue |
| FR | 226C0620 | VINPAI | 2026-05-04 | opa_simplifiee | 3.60 | verified_cash | (null) |
| FR | 226C0578 | POULAILLON | 2026-04-23 | opa_simplifiee | 9.00 | verified_cash | (null) |
| FR | 226C0538 | SOCIETE DE LA TOUR EIFFEL | 2026-04-17 | opr | 8.20 | verified_cash | (null) |
| FR | 226C0511 | GAUMONT | 2026-04-13 | opr | 90.00 | verified_cash | (null) |
| FR | 226C0287 | FNAC DARTY | 2026-03-12 | opa | 36.00 | verified_cash | (null) |
| FR | 226C0210 | GROUPE TERA | 2026-02-19 | opra | 6.50 | verified_cash | (null) |
| FR | 226C0156 | UV GERMI | 2026-02-05 | opra | 3.30 | verified_cash | (null) |
| DE | …KC01000… | Klöckner & Co SE | 2026-02-05 | opa_vol_tot | 11.00 | verified_cash | home_venue |
| FR | 226C0095 | SOCIETE DE TAYNINH | 2026-01-23 | opa_simplifiee | 0.11 | verified_cash | (null) |
| FR | 225C2061 | COGELEC | 2026-01-22 | opa_simplifiee | 29.00 | verified_cash | (null) |
| FR | 226C0008 | GROUPE TERA | 2026-01-05 | opra | 6.50 | verified_cash | (null) |
| FR | 225C2136 | UV GERMI | 2025-12-16 | opra | 3.30 | verified_cash | (null) |
| FR | 225C2081 | SOCIETE DE TAYNINH | 2025-12-08 | opa_simplifiee | 0.11 | verified_cash | (null) |

### Clusters uniques (score_deal agrège par target+jur)
6 cibles FR en double (multi-stage : FNAC DARTY, Tour Eiffel, Poulaillon, GROUPE
TERA, UV GERMI, Tayninh) → **9 clusters FR + 2 DE = 11 clusters** à scorer.

## Résolution ticker — **gap majeur**

- **15/15 FR ont `ticker_target` (ISIN) NULL** : l'extraction ISIN Phase 10 n'a
  jamais tourné sur ces deals frais. **OpenFIGI ne peut rien résoudre sans ISIN.**
  → Prérequis dur : extraire l'ISIN depuis le PDF AMF (méthode Phase 10) AVANT la
  résolution OpenFIGI. **PDF + source_url présents pour les 15** (extraction faisable).
- **2/2 DE déjà `home_venue`** (BaFin ISIN dans le ref) → tickers prêts.
- ⇒ Chaîne Step 1 (FR) : `p10 ISIN extraction → OpenFIGI resolve → persist`.
  Le nombre de FR `home_venue` (donc tradables) n'est connu qu'après résolution.

## Features scoring

- Modèle V1 dispo : `models/scoring_v1_20260526_p91c.pkl` ; `ScoringModel.load`.
- **Ne PAS retrain** (`score_deals_run.py` retrain+score tout) — charger V1 et ne
  scorer que les 11 clusters frais via `score_deal(deal_id, model, session)`.
- 1 event par deal (annonce). `premium_pct` NULL partout (non résolu/pricé) →
  NaN géré par l'IterativeImputer du V1. Scoring faisable tel quel ; la résolution
  Step 1 améliore le pricing/premium au moment de la décision (Step 3).
- Persist : table `scores` (pattern `_persist_score` de `score_deals_run.py`).

## Tradabilité potentielle (après chaîne complète)

Conditions cumulées : home_venue (FR) + score ≥3★ + offer_price présent + premium gate.
- **offer_price absent** : Tour Eiffel 226C0694, Poulaillon 226C0683 (mais leurs
  clusters ont une autre filing avec offer : 8.20 / 9.00 → OK au niveau cluster) ;
  **COMMERZBANK** `verified_mixed` sans scalaire (offre en titres ?) → probable
  non-tradable (le moteur exige un offer_price scalaire).
- **opra** (GROUPE TERA, UV GERMI) = rachats d'actions par la société elle-même,
  pas une prise de contrôle — le merger-arb tourne quand même (offre vs marché)
  mais à signaler.
- Plafond optimiste : ~8 clusters FR (hors opra/no-offer) + 1 DE (Klöckner) —
  sous réserve de résolution home_venue + score ≥3★.

## Vivacité — à vérifier manuellement

`expected_close_date` NULL partout (non renseignée). Annonces anciennes pour des
types à clôture rapide (opa_simplifiee/opra, 1-3 mois) → probablement **déjà
closes** malgré `completion_label` NULL :
- 225C2081 Tayninh (2025-12-08), 225C2136 UV GERMI (2025-12-16),
  226C0008 GROUPE TERA (2026-01-05), 225C2061 COGELEC (2026-01-22),
  226C0095 Tayninh (2026-01-23).
→ Marquer "vérifier vivacité" ; ne pas trader aveuglément si annonce > ~4 mois.

## Recommandation Step 1

1. Extraire l'ISIN des 15 FR via la méthode Phase 10 (parse PDF AMF, back-fill
   `ticker_target`) — adapter le filtre du script au pool frais (deals non
   labellisés, pas seulement "labelled").
2. Résoudre via OpenFIGI + persister ticker/flag (réutilise `ticker_resolution`
   de Phase 13).
3. Reporter combien de FR ressortent `home_venue` (tradables) vs growth/no_match
   (manual_review). C'est ce chiffre qui détermine le volume de décisions FR.
