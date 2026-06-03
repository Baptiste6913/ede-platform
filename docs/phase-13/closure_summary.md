# Phase 13 — Closure : FR unblock + actionable decision surface (IBKR decoupled)

## Executive summary

**Objectif.** Transformer EDE d'un auto-trader DE-only en **moteur de décision
actionnable** FR+DE : produire pour chaque OPA tradable une décision complète
(titre + ticker propre + entry + stop + take-profit + stratégie + rationale) que
l'opérateur lit avant d'exécuter manuellement — le calcul de décision **découplé
d'IBKR**, l'exécution paper IBKR conservée en aval pour le track record.

**Résultat.** ✅
- Calcul de décision **indépendant du broker** (prix de référence via yfinance,
  capital base configurable). IBKR paper devient une étape aval optionnelle
  (skip gracieux si Gateway down).
- **FR débloqué** au trading sous gate de confiance `home_venue` strict ;
  growth / venue_fallback / no_match / premium_out_of_bounds → manual_review.
- Ticker propre **persisté** (yfinance + IBKR) et résolu live pour les deals frais.
- Décision surfacée en **Markdown repo** (`artifacts/decisions/` + index) et en
  **embed Discord enrichi**, mêmes chiffres garantis par une source unique.

**Preuve end-to-end.** EUROBIO-SCIENTIFIC traverse toute la chaîne :
ISIN `FR0013240934` → OpenFIGI `home_venue` (ALERS.PA / ALERS@SBF) → gate FR
(passe) → décision (entry 24.97 / stop 22.48 / TP 25.30, 249 actions, 6.2 %) →
MD `artifacts/decisions/2026-06-03_FR0013240934_eurobio-scientific.md` + index +
embed Discord. Sans connexion IBKR.

---

## Methodology (Steps 1–5)

### Step 1 — Découpler IBKR du calcul (`refactor` ede3860)
Le prix de référence vient d'un `PriceProvider` non-broker
(`YFinancePriceProvider`, EOD close EUR) au lieu de `ibkr.get_current_price` ; le
sizing retombe sur `settings.trading_capital_base` quand le NetLiq IBKR est
indisponible. `run_daily_cycle` produit la décision (`CycleSummary.decisions`)
indépendamment, puis tente l'exécution paper **seulement si le broker est
disponible** (sinon `paper_execution_skipped`). `run_trading` connecte IBKR en
best-effort et tourne en mode décisions-only Gateway down.

### Step 2 — Persister le ticker OpenFIGI (`feat` 906fe31)
Migration **0017** ajoute `deals.trading_ticker_yf` (ticker yahoo, ex. `COVH.PA`),
distinct du `ibkr_ticker` broker (`COVH`) + `ibkr_exchange` (`SBF`) de 0011.
Nouveau `src/pricing/ticker_resolution.py` : résolution OpenFIGI → persistance
(yahoo + symbol/exchange IBKR dérivés + flag), câblée live dans `load_candidates`
(deal frais `flag NULL` → résolu une fois, cache-hit ensuite). Backfill
`p13_backfill_tickers.py` (cache-first, 0 appel API) : **130 FR + 33 DE**
tickers persistés, dont **35 FR home_venue** priceable. Les flags de traitement
(`premium_out_of_bounds` / `no_price_data` / `manual_review`) sont **préservés**
→ la protection premium de Phase 11 n'est pas défaite.

### Step 3 — Gate de confiance + FR unblock (`feat` ef58a32)
`TRADING_ALLOWED_JURISDICTIONS` = `[DE, FR]`. Nouveau setting
`trading_home_venue_strict_jurisdictions=[FR]` : dans une juridiction gatée, un
deal est auto-tradable **ssi** `ticker_resolution_flag == home_venue`. Le gate
tourne **après** la résolution live. DE n'est pas gaté (path ISIN BaFin fiable —
V1 inchangé).

| Juridiction | flag | Résultat |
|---|---|---|
| DE | home_venue / NULL / unknown_exch | tradable (inchangé) |
| FR | `home_venue` | **tradable (nouveau)** |
| FR | growth / venue_fallback / premium_oob / no_match / unknown_exch | manual_review |
| IT | — | exclu en amont (hors `allowed_jurisdictions`) |

### Step 4 — Surface décision MD (`feat` 349d8cf)
`src/output/decision_md.py` : un fichier MD lisible par décision
(`artifacts/decisions/{date}_{ISIN}_{slug}.md`) + `INDEX.md` cumulatif (upsert
idempotent, trié date décroissante). Champs manquants → `N/A`. Émis par un
`DecisionSink` injectable, best-effort, indépendant de l'exécution.

### Step 5 — Discord enrichi (`feat` 0282ca3)
`DiscordAlerts.decision_alert` : embed (titre, Ticker IBKR/yfinance,
Entry/Stop/TP, Sizing, Score+proba, Premium, Stratégie, footer filing+MD). MD ↔
Discord **cohérents par construction** : tous deux consomment
`decision_md.decision_view(req, deal)`, source unique des champs formatés.

---

## Architecture finale

```
Nouvelle OPA → parse + score + premium (SANS IBKR)
            → résolution OpenFIGI (ticker propre persisté) → gate de confiance
            → calcul décision (entry/stop/TP/sizing/rationale, prix yfinance)
            → décision produite
                 ├─ MD Obsidian/repo + INDEX            [toujours]
                 ├─ embed Discord                        [toujours, best-effort]
                 ├─ persist DB (flags, ticker)           [toujours]
                 └─ exécution paper IBKR                 [aval, optionnel, gracieux]
```

---

## Scope honnête

- **FR home_venue tradable = forward-looking.** Aucun deal FR ouvert n'est scoré
  ≥ 3★ aujourd'hui (582 FR ouverts non scorés ; seuls 2 DE ouverts scorés). La
  valeur est sur les **nouvelles OPA FR**, résolues automatiquement par le câblage
  live. Le pipeline FR est prouvé (tests), pas alimenté par un stock existant.
- **Scoring des deals ouverts** = contrainte amont hors périmètre Phase 13 : sans
  scoring des 582 FR ouverts, aucune décision FR réelle ne sortira. Chantier suivant.
- **IT** en attente de l'extraction ISIN Consob (exclu en amont).
- **FR growth / venue_fallback** délibérément en manual_review (home_venue strict).

## Tech debt P14+ (inchangé)

1. Extraction ISIN IT/Consob → débloquer IT.
2. Scoring live des deals ouverts (prérequis opérationnel du FR unblock).
3. Premium coverage des small/mid caps EU délistées (source prix alternative).
4. Parser `offer_price` corrompus + re-parse (COVIVIO, VOGO, ALBA, Turbon).
5. Cross-check identité dans le resolver (rejeter wrong-references main-market).
6. V2 retrain quand la couverture premium le justifie.

## Commits

| Commit | Résumé |
|---|---|
| `25ee6f0` | docs: Step 0 preflight (diagnostic FR) |
| `ede3860` | refactor: découplage IBKR / calcul |
| `906fe31` | feat: persistance ticker OpenFIGI + résolution live |
| `ef58a32` | feat: gate confiance home_venue + FR unblock |
| `349d8cf` | feat: surface décision MD + index |
| `0282ca3` | feat: Discord enrichi |
| _this_ | docs: closure |

## Artifacts

- `artifacts/phase-13/preflight.md` — diagnostic Step 0.
- `artifacts/phase-13/ticker_backfill_audit.md` — backfill (130 FR / 33 DE).
- `artifacts/decisions/` — décisions actionnables + INDEX (témoin EUROBIO).
