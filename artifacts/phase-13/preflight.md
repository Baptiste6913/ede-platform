# Phase 13 — Step 0 preflight : débloquer FR main-market pour le trading

But Phase 13 : produire des **décisions actionnables** (titre + ticker propre +
entry + stop + stratégie + rationale) sur les deals FR où OpenFIGI résout en
home_venue. Growth / no_match → manual_review.

> **Statut DB** : Postgres tourne sous Docker (`docker compose`), **daemon Docker
> down au moment du diagnostic**. Les chiffres deal-level (join score + statut
> ouvert) sont donc marqués `⧗ DB`. Tout le reste est dérivé du code source et du
> cache de résolution Phase 11 sur disque (`artifacts/phase-11/openfigi_cache.json`),
> qui est la source autoritaire de la résolution ISIN→ticker.

---

## 0. État Git

- `main` à jour avec `origin/main` (HEAD `a8e5216`, merge PR #19 phase-12).
- **`phase-12b` PAS mergée** : 3 commits d'avance sur main
  (`ef5100e`, `278d84f`, `6e30fb4`).
  - Contenu = **closure analytique uniquement** : un script de cross-check
    (`scripts/p12b_growth_crosscheck_preflight.py`), des artifacts, le doc de
    closure. **Aucun changement de code de prod** (décision actée : V1 reste,
    pas de retrain V2).
  - **Phase 13 n'en dépend pas** : elle s'appuie sur le resolver OpenFIGI
    (Phase 11) et l'extraction ISIN FR (Phase 10), tous deux déjà dans `main`.
  - Reco : merger phase-12b via PR pour fermer proprement l'historique
    (housekeeping, non bloquant). Sinon l'abandonner — neutre fonctionnellement.
- Travail Phase 13 démarré sur branche `phase-13-fr-unblock`.

---

## 1. Distribution des résolutions (source = cache OpenFIGI Phase 11, 93 ISINs)

| Juridiction | home_venue | venue_fallback | home_venue_growth | no_match | unknown_exch | **Total ISIN** |
|---|---:|---:|---:|---:|---:|---:|
| **DE** | 25 | 1 | 0 | 1 | 8 | 35 |
| **FR** | 21 | 2 | 28 | 5 | 2 | 58 |
| **IT** | 0 | 0 | 0 | 0 | 0 | 0 (no-ISIN ⇒ `not_isin`) |

Cohérent avec l'audit Phase 11 (`home_venue` deal-level = 46 = 25 DE + 21 FR).

### FR résolus en main-market (ticker propre, haute confiance) — 23 ISIN

21 `home_venue` (exch FP → `.PA`) + 2 `venue_fallback`. Exemples : `OVH.PA`,
`WAGA.PA` (Waga Energy), `UNBL.PA` (Unibail), `VRLA.PA`, `TRACT.PA`, `AURE.PA`…

**Caveats sur ces 23 :**
- **2 ISIN FR cotés sur Xetra** (`FR0014003FE9`→`8T6.DE`, `FR0014005DA7`→`97K.DE`) :
  émetteur FR mais venue DE → ticker propre mais exchange = IBIS, pas SBF.
  ⇒ FR-ISIN ≠ FR-venue : le mapping exchange doit suivre l'exch BBG, pas l'ISIN.
- **3 ISIN flaggés `premium_out_of_bounds` en DB** malgré une résolution
  home_venue : `COVH.PA` (Covivio), `ALVGO.PA` (VOGO ×2 deals), `EEM.PA`
  (Électricité et Eaux). Le flag persisté en DB devient `premium_out_of_bounds`,
  **pas** `home_venue` → un gate sur le flag les exclut automatiquement (offre
  corrompue, cf. backlog Phase 12b). C'est le comportement voulu.

⇒ **FR home_venue réellement propres (offre saine) ≈ 18 ISIN.**

---

## 2bis. Résultats DB (Docker up) — chiffres autoritaires

> Requêtes lancées via `docker exec ede-postgres psql`. Le Bash git-bash ne joint
> pas le npipe Docker ; passer par PowerShell.

### Deals × juridiction × flag de résolution

| Jur. | (null) | home_venue | growth | no_match | no_price_data | premium_oob | unknown_exch | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FR | **582** | 35 | 72 | 12 | 19 | 4 | 6 | 730 |
| IT | 47 | 0 | 0 | 0 | 0 | 0 | 0 | 47 |
| DE | 3 | 11 | 0 | 1 | 17 | 2 | 8 | 42 |

### Deals OUVERTS (completion_label NULL) + scoring

| Jur. | ouverts | ouverts **non scorés** | ouverts scorés ≥3★ |
|---|---:|---:|---:|
| FR | 582 | **582** | **0** |
| IT | 12 | 12 | 0 |
| DE | 3 | 1 | 2 (5★) |

- `ibkr_ticker` peuplé : **0 / 819** sur les 3 juridictions (jamais persisté — confirmé).
- Seuls **2 deals ouverts sont scorés** (DE, 5★) — et leur flag = `(null)`.

### Conséquences SCOPE (importantes)

1. **Backlog FR tradable immédiat = 0.** Aucun deal FR n'est scoré ≥3★. La valeur
   du FR unblock est **100 % forward-looking** (nouvelles OPA), pas un stock à
   débloquer.
2. **582 deals FR ouverts NON SCORÉS** : le scoring ne tourne pas sur les deals
   ouverts. C'est la vraie contrainte amont — hors périmètre Phase 13 (trading),
   mais sans scoring des deals ouverts, **aucune décision FR ne sortira**, quel
   que soit l'unblock. À flaguer comme chantier suivant (pipeline scoring live).
3. **Le gate `ticker_resolution_flag == 'home_venue'` (Step 3) STARVE le pipeline
   s'il s'appuie sur le flag de backfill** : tous les `home_venue` sont des deals
   CLOS (training), les 2 deals ouverts ont flag `(null)`. ⇒ **la résolution doit
   se faire au moment de la décision (live)** et écrire le flag, sinon le gate
   exclut tout deal frais. Step 2 (résolution des deals frais) est donc
   **prérequis dur** de Step 3, pas un nice-to-have.

---

## 2. Combien de deals FR tradables *immédiatement* ?  ⧗ DB  → RÉPONDU §2bis : **0**

**Nuance critique.** Les 187 deals backfillés en Phase 11 sont en grande majorité
**historiques (labellisés)** — ils ont servi à entraîner le modèle. Or le pipeline
de trading ne prend que les deals **ouverts** :

```python
# scheduler.load_candidates
Score.score_stars >= min_stars            # ≥ 3★
Deal.completion_label.is_(None)           # deal NON clos
Deal.offer_price_quality_flag.not_in(UNTRADEABLE_OFFER_PRICE_FLAGS)
# + filtre juridiction (allowed_jurisdictions)
```

Donc « 18-21 FR home_venue » est une mesure de **capacité** (le pipe FR résout),
pas du **backlog tradable**. Le nombre de FR **ouverts + score ≥ 3** est
probablement faible (le backfill était rétrospectif) et **nécessite la DB** :

```sql
-- À lancer Docker up (queries read-only, prêtes) :
SELECT juridiction, ticker_resolution_flag, COUNT(*)
FROM deals GROUP BY 1,2 ORDER BY 1,2;

SELECT d.juridiction, d.ticker_resolution_flag,
       (d.completion_label IS NULL) AS open, COUNT(*)
FROM deals d JOIN scores s ON s.deal_id=d.id
WHERE s.score_stars >= 3
GROUP BY 1,2,3 ORDER BY 1,2,3;
```

La vraie valeur de Phase 13 est **forward-looking** : chaque nouvelle OPA FR
main-market produira désormais une décision. Le backlog immédiat se compte une
fois Docker up.

---

## 3. Format de décision actuel vs cible

### Ce qui existe déjà (riche) — `TradeRequest` (`decision_engine.py`)

Le moteur produit DÉJÀ tous les champs nécessaires :

| Champ cible Baptiste | Présent ? | Source dans `TradeRequest` |
|---|---|---|
| Titre (deal) | ✅ | `deal_target` / `deal_acquirer` |
| Ticker propre | ⚠️ partiel | `symbol` + `exchange` — **souvent `None`** (voir §4) |
| Entry | ✅ | `limit_price` = ref × (1 + 0.1 % FR/DE) |
| Stop | ✅ | `stop_loss_price` = entry × 0.90 |
| Take-profit | ✅ | `take_profit_price` = offer_price |
| Stratégie | ⚠️ implicite | merger-arb long-only (jamais labellisé en sortie) |
| Rationale | ✅ | `rationale` (p_completion, spread, Kelly, qty@limit) |
| Sizing | ✅ | `quantity`, `kelly_fractional_pct`, `position_pct` |

### Ce que Baptiste VOIT réellement aujourd'hui — Discord (`discord_alerts.py`)

```
🟢 New trade pending approval (ramp-up 1/5): {deal_target} buy {qty} @ {price:.2f}
```

**Gap : le Discord ne sort que titre + qty + limit.** Pas de ticker, pas de stop,
pas de take-profit, pas de rationale, pas de stratégie — alors que tout existe
dans `TradeRequest`. L'objet riche est construit puis **réduit** à l'alerte.

### Gap supplémentaire — le pipeline AUTO-EXÉCUTE

Le flux actuel (`run_trading.py` → `scheduler.run_daily_cycle` →
`executor.submit`) **soumet les ordres à IBKR paper** ; le Discord est une
notification, pas un livrable de décision pour exécution manuelle. De plus,
**le calcul d'une décision exige une connexion IBKR live** (le snapshot de prix
de référence vient de `ibkr.get_current_price`).

⇒ Si l'objectif est « décisions que J'EXÉCUTE MANUELLEMENT dans mon broker », il
faut décider (Step 1) : (a) garder l'auto-exécution paper + enrichir la sortie,
ou (b) ajouter une **surface décision** (carte actionnable : fichier MD / Discord
enrichi) découplée d'IBKR, avec prix de réf via yfinance (déjà dans la stack)
plutôt qu'IBKR.

---

## 4. Le ticker propre n'est PAS persisté — cœur du blocage FR

Chaîne de résolution du trading (`trading/ticker_resolver.py`) :

```
1. cache   : deals.ibkr_ticker + deals.ibkr_exchange   → ticker propre direct
2. manual  : ticker_mapping.json (5 entrées seulement)
3. isin    : ISIN extrait de regulator_ref / ticker_target → IBKR qualifie par ISIN
4. None    : manual_review
```

**Constat décisif : la résolution OpenFIGI Phase 11 n'écrit JAMAIS
`ibkr_ticker` / `ibkr_exchange`.** Le backfill (`p11_full_backfill.py`) ne
persiste que `ticker_resolution_flag`, `reference_price_*`, `premium_pct`. Le
ticker propre (`yahoo_ticker`, ex. `COVH.PA`) ne vit que dans le **cache disque**
et le MD d'audit.

Conséquences pour un deal FR aujourd'hui :
- chemin **cache** : `ibkr_ticker`/`ibkr_exchange` = `NULL` → sauté.
- chemin **manual** : seulement si dans les 5 entrées du JSON.
- chemin **isin** : `ticker_target` = l'ISIN FR (Phase 10) → résout **par ISIN**,
  exchange = SBF. IBKR qualifie le contrat → **l'exécution marche**, mais
  `TradeRequest.symbol = None` → **aucun ticker propre dans la sortie**. ❌

(Idem DE aujourd'hui : passe par le chemin ISIN, `symbol=None`, IBKR qualifie en
interne — Baptiste n'a pas de ticker propre affiché non plus.)

### + Le flag de confiance n'existe pas en live

`home_venue` vs `home_venue_growth` est calculé par le **resolver OpenFIGI**, qui
n'est **pas câblé dans le chemin trading**. Le `ticker_resolution_flag` est un
artefact de **backfill rétrospectif** : un nouveau deal FR ouvert aura le flag
`NULL`. Donc **on ne peut pas gater le trading live sur `ticker_resolution_flag`
seul** — il faut soit faire la résolution OpenFIGI au moment de la décision, soit
la persister (ticker + flag) à l'ingestion/scoring.

---

## 5. Recommandations pour Step 1

Le déblocage FR n'est PAS un simple flip d'`allowed_jurisdictions`. 3 chantiers :

1. **Persister le ticker propre OpenFIGI dans `ibkr_ticker` / `ibkr_exchange`**
   (+ exchange IBKR dérivé de l'exch BBG : FP→SBF, GR/GY→IBIS, IM→BVME).
   - Backfill one-shot depuis le cache OpenFIGI pour les FR home_venue existants.
   - **Câbler la résolution OpenFIGI dans le flux live** (ingestion/scoring ou
     `load_candidates`) pour que tout nouveau deal FR obtienne ticker + flag de
     confiance — sinon le gate exclut tous les deals frais.
2. **Gate de sécurité sur la confiance** dans `load_candidates` : auto-tradable
   ssi confiance ∈ {home_venue, venue_fallback}. Growth / no_match / unknown_exch
   / premium_out_of_bounds → `manual_review` (exclus). Reprend le garde-fou
   anti-collision (ALCLA.PA = Claranova) et exclut déjà les offres corrompues.
3. **Surface de décision actionnable** (décision produit, à trancher Step 1) :
   sortir titre + ticker + exchange + entry + stop + TP + stratégie + rationale —
   soit en enrichissant le Discord, soit dans un fichier décision (Obsidian /
   `artifacts`), et décider du couplage IBKR (auto-paper vs sortie manuelle +
   réf de prix yfinance).
4. Puis seulement : `TRADING_ALLOWED_JURISDICTIONS=DE,FR`.

### Questions ouvertes pour Baptiste (Step 1)

- **Q1 — Exécution** : on garde l'auto-soumission IBKR paper (+ on enrichit la
  notif), ou on bascule vers une **sortie décision pure** que tu exécutes à la
  main (et on découple IBKR du calcul, prix de réf via yfinance) ?
- **Q2 — Surface** : carte décision où ? Discord enrichi / fichier MD dans le
  vault Obsidian / les deux ?
- **Q3 — Périmètre confiance** : on inclut `venue_fallback` (2 deals FR) avec les
  `home_venue`, ou strictement `home_venue` ?

---

## Annexe — fichiers clés

- `src/trading/scheduler.py::load_candidates` — filtre juridiction + statut.
- `src/trading/decision_engine.py::evaluate_candidate` — entry/stop/TP/rationale.
- `src/trading/ticker_resolver.py` — chaîne cache→manual→isin (pas de confiance).
- `src/pricing/openfigi_resolver.py` — résolution home_venue + flag (hors trading).
- `src/core/settings.py::trading_allowed_jurisdictions` — défaut `["DE"]`.
- `artifacts/phase-11/openfigi_cache.json` — résolution autoritaire (93 ISIN).
