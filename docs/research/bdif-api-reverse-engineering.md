# BDIF AMF — API reverse engineering

> **Status**: API confirmed publicly accessible without authentication. Implementation path: direct HTTP via `httpx` (no Playwright needed).
> **Discovered**: 2026-05-13 (phase 3).

---

## 1. Front-end

- URL (entrée utilisateur): `https://bdif.amf-france.org/Recherche-avancee?formId=BDIF`
- Redirige vers: `https://bdif.amf-france.org/fr?xtor=AL-26` (302)
- Stack: Angular 17 + Angular Material (SPA, 49 KB d'HTML bootstrap + bundles JS)
- Données chargées par XHR après hydration JS.

## 2. Akamai bot challenge — bypass possible

Le site sert des POST opaques (URLs base64-like `/7gew_eyP5n4OtprGo9m9dRPcEpZB76dfiof-...`) qui sont des challenges Akamai Bot Manager exécutés silencieusement par le navigateur. **Le headless Chrome les résout automatiquement** (vu via chrome-devtools MCP).

**Bonne nouvelle**: les endpoints `/back/api/v1/*` répondent `200 OK` **sans** ces cookies de challenge, à condition d'envoyer :

- `User-Agent` réaliste (Chrome desktop accepté)
- `Accept: application/json`
- `Accept-Language: fr-FR,fr;q=0.9`
- `Referer: https://bdif.amf-france.org/fr`

Test confirmé en local avec `curl` natif (pas de cookies persistants):

```
$ curl -i "https://bdif.amf-france.org/back/api/v1/informations?From=0&Size=5" \
       -H "User-Agent: Mozilla/5.0 ... Chrome/147 ..." \
       -H "Accept: application/json" \
       -H "Accept-Language: fr-FR,fr;q=0.9" \
       -H "Referer: https://bdif.amf-france.org/fr"
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: 34124
```

**Conséquence**: pas besoin de Playwright. Le poller utilise `httpx.AsyncClient` directement, partage la même librairie que le RSS watcher.

## 3. Endpoint principal — `GET /back/api/v1/informations`

### Paramètres query

| Nom | Type | Description |
|---|---|---|
| `From` | int | Offset (pagination, 0-indexé) |
| `Size` | int | Taille de page (testé jusqu'à 100, par défaut 20) |
| `typesInformation` | string (répétable) | `OPA`, `OPV`, `FT`, `Pactes`, etc. (clés des buckets d'agrégation) |
| `typesDocument` | string (répétable) | `NotesEtAutresInformations` (M&A doc), `DepotOffre`, `CalendrierOffre`, `ResultatOffre`, `DeclarationAchatVente`, `Decisions`, `RetraitObligatoire`, `PreOffre`, etc. |
| `typesOperation` | string (répétable) | `OPA`, `OPAS`, `OPE`, `OPR`, `OPRA`, `OPRRO`, `OPES`, `OPAGC`, `PreOffre`, `RO`, etc. |
| `marche` | string (répétable) | `Euronext`, `EuronextGrowth`, `Alternext`, `MarcheLibre` |
| `dateDebut` | YYYY-MM-DD | Date min de publication (à confirmer) |
| `dateFin` | YYYY-MM-DD | Date max de publication (à confirmer) |
| `keyword` | string | Recherche texte libre (autocompletion sur sociétés / refs) |

### Headers obligatoires

```
User-Agent: <Chrome desktop>
Accept: application/json
Accept-Language: fr-FR,fr;q=0.9
Referer: https://bdif.amf-france.org/fr
```

### Réponse — top-level

```json
{
  "total": 10000,        // total matching (capped at 10k by ES)
  "result": [ /* page items */ ],
  "aggregations": { /* buckets pour faceting */ }
}
```

### Item shape (extrait par item)

```json
{
  "id": 366036,
  "numero": "2026DD1114393",          // BDIF-internal ref (varies by type)
  "numeroSOIF": null,
  "numeroConcatene": "2026DD1114393",
  "domaine": "DOP",                    // DOP / DROP
  "regulateur": "AMF",
  "roleRegulateur": "Document",
  "indexYear": 2026,
  "langue": "FR",
  "version": 1,
  "dateCreation":     "2026-05-13T18:08:04.593",
  "datePublication":  "2026-05-13T18:08:05.4443196+02:00",
  "dateAction":       null,
  "dateMiseEnLigne":  "2026-05-13T18:08:04.34",
  "dateInformation":  "2026-05-13T00:00:00",
  "typesDocument":    ["DeclarationDirigeants"],
  "typesInformation": ["DD"],
  "typesOperation":   [],
  "documents": [
    {
      "nomFichier": "DD_26_1114393_12210685.pdf",
      "accessible": true,
      "docRegulateur": true,
      "path": "2026/2026DD1114393/0DE6C0F4...AFD9.pdf",   // RELATIVE PATH for /documents/
      "signature": "<base64 RSA signature>",
      "dateReception": null
    }
  ],
  "societes": [
    {
      "jeton": "RS00007437",
      "raisonSociale": "GROUPE AIRWELL",
      "role": "SocieteConcernee"        // or "SocieteVisee" / "Initiateur" for M&A
    }
  ]
}
```

### Pagination

- Pas de cursor — offset numérique via `From`.
- Limite ES: `total` ≤ 10000. Au-delà il faut affiner les filtres (date range).

## 4. Endpoint document — `GET /back/api/v1/documents/{path}`

Le `path` du sous-objet `documents[].path` se concatène simplement:

```
https://bdif.amf-france.org/back/api/v1/documents/{item.documents[0].path}
```

Test (Fnac Darty note d'information OPA, BDIF numero `226C0644`):

```
$ curl -L "https://bdif.amf-france.org/back/api/v1/documents/2026/226C0644/72DF20...A90C.pdf" \
       -H "User-Agent: ..." -H "Accept-Language: fr-FR,fr;q=0.9" \
       -H "Referer: https://bdif.amf-france.org/fr"
HTTP/1.1 200 OK
Content-Type: application/pdf
142007 bytes
%PDF-1.7
```

## 5. Rate limit observé

Test empirique: 10 requêtes successives à 1 Hz → 0 erreur, pas de slowdown.
Notre poller garde la même politique conservative que phase 2:
- 1 req/s + jitter [0, 200ms]
- exponential backoff sur 429/5xx (réutilisation de `src/ingestion/amf/rate_limiter.py`)
- timeout 30s, 3 retries

## 6. Filtrage M&A — combinaison retenue

Pour récupérer **les notes d'information** (documents officiels déposés par les initiateurs) :

```
GET /back/api/v1/informations
  ?From=0
  &Size=20
  &typesInformation=OPA
  &typesDocument=NotesEtAutresInformations
```

Résultat 2026-05-13: **1786 notes** au total (depuis 1997). Sur les 12 derniers mois, on attend ~30-60 notes (corroboré par les 5 premières dates : 11 mai, 7 mai, 12 mai, 4 mai, 28 avril → 5 notes en 17 jours).

### Échantillon top-5 (2026-05-13)

| numero | datePub | typesOperation | société |
|---|---|---|---|
| 226C0661 | 2026-05-11 | OPR | MEDIA 6 |
| 226C0645 | 2026-05-07 | OPR | MEDIA 6 |
| 226C0644 | 2026-05-12 | OPA | **FNAC DARTY** |
| 226C0620 | 2026-05-04 | OPAS | VINPAI |
| 226C0591 | 2026-04-28 | OPA | ELECTRICITE ET EAUX DE MADAGASCAR |

## 7. Mapping vers le schéma EDE

| BDIF field | EDE `deals` column | Note |
|---|---|---|
| `numero` | `regulator_ref` | Real ref (no synthetic `AMF-SYN-*` anymore) |
| `societes[?role=SocieteVisee].raisonSociale` | `target_name` | |
| `societes[?role=Initiateur].raisonSociale` | `acquirer_name` | |
| `dateInformation` | `announcement_date` | |
| `typesOperation[0]` | `deal_type` (mapped) | OPA→`opa`, OPAS→`opa_simplifiee`, OPE→`ope`, OPR→`opr`, OPRA→`opra`, OPRRO→`opr_ro`, OPAGC→`garantie_de_cours` |
| `documents[0].path` | `pdf_path` (after download) | Atomic write to `data/pdfs/fr/{year}/{numero}.pdf` |

## 8. Tech debt phase 2 closed by this approach

- ✅ **Real `regulator_ref`** (`numero` field) instead of synthetic `AMF-SYN-*`.
- ✅ **Real BDIF PDFs** downloaded (Fnac Darty etc.) instead of 0 PDFs.
- ✅ **Tight M&A filter** at the API layer (no regex false positives on "Communiqués AMF").
- ✅ **Direct HTTP** — no Playwright, no headless browser dependency in prod.

## 9. Open questions / future-work

1. **Date filtering**: query params `dateDebut`/`dateFin` not verified yet — we'll use client-side filtering on `datePublication` and `From=0&Size=100` pagination until proven needed.
2. **Cross-jurisdiction overlap**: a DE filing on Euronext-Paris-listed target could appear here. Combine with `marche` filter in phase 4.
3. **Visa AMF in PDF**: the `numero` here is BDIF-internal. The "visa AMF" stamp inside the PDF (e.g. "AMF-26-128") is a separate identifier extracted by the parser from the PDF text.
4. **PreOffre** documents: `typesDocument=PreOffre` represents early-stage rumours / forced disclosures — not real filings but useful as early signal. Could be ingested with `has_document=true` but a different `event_type` later.
