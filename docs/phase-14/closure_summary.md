# Phase 14 — Closure : fresh deal pipeline → 1 tradable decision (FNAC DARTY)

## Executive summary

**Objectif.** Faire tourner le système Phase 13 sur les OPA FR+DE **fraîches**
(plausiblement ouvertes) pour qu'il produise des décisions actionnables que
l'opérateur inspecte et trade manuellement — pas de scoring de masse des 730 FR
historiques.

**Résultat.** ✅ Pipeline end-to-end prouvé sur le pool frais :
OPA fraîche → extraction ISIN → résolution OpenFIGI (home_venue) → score V1 →
premium réel (yfinance) + gate → **décision MD/Discord, sans IBKR**.
**1 décision tradable nette : FNAC DARTY** (spread résiduel 4.3 %). 6 candidats
filtrés — pour de bonnes raisons.

**Le filtrage est le résultat, pas l'échec.** Sur 7 candidats ≥3★ : 4 écartés car
spread < 1 % (prix courant ≈ offre, plus d'edge merger-arb), 1 sans prix yfinance
T-1 (COGELEC), 1 au premium gate (TAYNINH −95.3 %, offre corrompue). Le système
**discrimine correctement** les deals sans opportunité, sans data, ou à prix aberrant.

---

## Methodology (Steps 0–3)

### Step 0 — Pool frais isolé (`docs` 38552d8)
Critère : FR+DE, `announcement_date ≥ 2025-12-03`, `completion_label NULL`,
`status='announced'`. **17 deals live** (15 FR + 2 DE) → **11 clusters** (dédup
multi-stage). 17 FR fraîches déjà closes exclues. Gap identifié : les 15 FR ont
`ticker_target` (ISIN) NULL.

### Step 1 — Extraction ISIN + résolution (`feat` 03cf068)
Réutilise l'extraction PDF Phase 10 + la résolution OpenFIGI Phase 13 sur le pool
frais. **15/15 FR ISIN extraits**, **15/15 résolus `home_venue`** avec ticker
propre (EIFF.PA, FNAC.PA, GAM.PA, ALPOU.PA, ALVIN.PA, ALUVI.PA, ALGTR.PA,
ALLEC.PA, TBSO.PA). Les mnémoniques Growth (AL…) résolus via le **composite FP**
(pas le path currency-strippé) → haute confiance, pas de collision. 2 DE déjà
home_venue (BaFin). Tech debt P15 : extraction non câblée dans l'ingestion live.

### Step 2 — Scoring V1 (`feat` 80f6f3d)
Modèle V1 existant (`scoring_v1_20260526_p91c.pkl`, **pas de retrain**), score
cluster-level persisté sur le deal frais le plus récent home_venue+offre.
**8 clusters ≥3★** (4×5★, 4×4★, 3×2★).
**CAVEAT** : le V1 discrimine essentiellement par **type de deal** — `premium_pct`
et les features de prix sont NaN (imputées) sur ces deals frais non encore pricés.
Le score seul ne sépare pas deux deals de même type ; le signal fin vient du
premium réel (Step 3).

### Step 3 — Premium réel + décisions (`feat` b65b5ed)
Par candidat : premium takeover calculé yfinance (réf T-1 vs offre) + persisté +
gate `[-50 %, +200 %]` ; puis prix courant comme référence de décision → moteur
(entry/stop/TP/sizing) → émission MD + index + Discord. **Sans IBKR.**

**7 candidats → 1 décision :**
- ✅ **FNAC DARTY** (FNAC.PA, 5★) — premium 5.1 % (36.00 vs 34.25), prix courant
  34.50, **spread 4.3 %**, entry 34.53 / stop 31.08 / TP 36.00, 347 actions
  (~12 k €, 12 % du capital).
- ⊘ Tour Eiffel, Klöckner (DE), Poulaillon, Gaumont → spread < 1 % (pas d'edge).
- ⊘ COGELEC → pas de prix yfinance T-1.
- ⊘ TAYNINH → premium −95.3 % → `premium_out_of_bounds` (offre 0.11 corrompue/split).
- *(COMMERZBANK écarté en amont : `verified_mixed`, offre en titres, pas de scalaire.)*

---

## Bilan

Le pipeline Phase 13 fonctionne en conditions réelles sur des deals frais : il
résout, score, price, gate et produit une décision actionnable lisible, sans
dépendance broker. La rareté des décisions (1/7) reflète l'état du marché (la
plupart des OPA fraîches se tradent au ras de l'offre), pas un défaut du système.

## Insights

1. **Le système discrimine correctement** : il écarte les deals sans edge
   (spread < 1 %), sans data, ou à prix corrompu — exactement le comportement
   voulu pour un signal actionnable.
2. **Le premium réel (pas le score V1) est le signal discriminant** entre deals
   de même type. Le V1 sépare par type ; le premium yfinance sépare au sein d'un
   type. C'est lui qui fait remonter FNAC DARTY.
3. **Le gate premium a attrapé une offre corrompue en production** (TAYNINH
   −95.3 %) — la défense Phase 11/13 tient sur des données fraîches.

## Tech debt P15+

1. **Câbler l'extraction ISIN dans l'ingestion live** (auto-traiter tout futur
   deal FR ; aujourd'hui one-shot backfill).
2. **offer_price corrompus** : TAYNINH (0.11) + historiques (COVIVIO, VOGO, ALBA,
   Turbon) — parser hardening + re-parse PDF.
3. **premium coverage / V2** : le V1 ne discrimine que par type ; un modèle avec
   premium dense séparerait mieux (dépend de la couverture prix small caps).
4. **no_price_data recovery** : COGELEC et small caps illiquides sans série
   yfinance T-1 — source prix alternative.
5. **Vérification vivacité automatique** : lire les filings récents (clôture /
   résultat) plutôt que se fier à `completion_label` non backfillé + la date.

## Commits

| Commit | Résumé |
|---|---|
| `38552d8` | docs: Step 0 preflight (pool frais) |
| `03cf068` | feat: extraction ISIN + résolution (15/15 home_venue) |
| `80f6f3d` | feat: scoring V1 (8 ≥3★) |
| `b65b5ed` | feat: génération décisions (1 nette — FNAC DARTY) |
| _this_ | docs: closure |

## Artifacts

- `artifacts/phase-14/preflight.md` — pool frais.
- `artifacts/phase-14/isin_resolution_fresh.md` — 15/15 home_venue.
- `artifacts/phase-14/scoring_audit.md` — 11 clusters, 8 ≥3★.
- `artifacts/phase-14/decisions_generated.md` — 1 décision, 6 filtrées.
- `artifacts/decisions/2026-06-03_FR0011476928_fnac-darty.md` + INDEX.
- Scripts : `p14_resolve_fresh.py`, `p14_score_fresh.py`, `p14_decide_fresh.py`.
