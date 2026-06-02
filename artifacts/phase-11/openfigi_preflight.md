# Phase 11 Pre-Flight — OpenFIGI Evaluation

Branch: `phase-11-openfigi-resolver` (from main HEAD `084e59b`)
Date: 2026-06-02 | Probe: 3 sample ISINs from the Phase 10 sample (Step 0, no resolver code)

## API Summary

- **Endpoint**: `POST https://api.openfigi.com/v3/mapping`
- **Auth header**: `X-OPENFIGI-APIKEY: ${OPENFIGI_API_KEY}` (+ `Content-Type: application/json`)
- **Request**: JSON array of jobs, each `{idType, idValue, exchCode?}`. Up to 100 jobs/request with key.
- **idType**: `ID_ISIN`, `ID_BB_GLOBAL` (FIGI), `TICKER`, … — we use `ID_ISIN`.
- **Rate limits**: 25 req/min, 1000 req/day (with key). 187-deal backfill ≈ 8 batched requests → trivial.
- **Response**: array, 1 element per job. Match → `{"data": [ …rows… ]}`; miss → `{"warning": "No identifier found."}`; bad job → `{"error": "..."}`.
- **Useful data fields**: `ticker`, `exchCode`, `securityType`, `marketSector`, `securityDescription`, `name`, `figi`, `compositeFIGI`, `shareClassFIGI`.

### ⚠️ Major correction vs the brief — exchCode is Bloomberg, not MIC

The brief assumed MIC codes (XPAR/MTAA/GY). **OpenFIGI uses Bloomberg 2-letter exchange codes.** MIC hints return zero matches:

| Jurisdiction | Brief said (MIC) | Result | Actual Bloomberg exchCode |
|---|---|---|---|
| Paris | `XPAR` | **0 matches** ("No identifier found") | `FP` |
| Milano | `MTAA` | **0 matches** | `IM` |
| Xetra | `GY` | **1 match ✓** (coincidentally correct) | `GY` (composite `GR`) |

This reshapes Step 1: any exchCode hinting must use Bloomberg codes (FP, IM, GY/GR, …), and the safest path is to **query without exchCode and filter the result set** (see Recommendations).

## Sample Tests

### Test 1 — Mediobanca `IT0000062957`
- **No exchCode**: HTTP 200, **941 ms**, **111 matches**. First row = primary listing:
  `{figi: BBG000BBKYH7, ticker: "MB", exchCode: "IM", compositeFIGI: BBG000BBKY05, securityType: "Common Stock", marketSector: "Equity"}`.
  All 111 rows share `shareClassFIGI BBG001S60MR5` → same security, many venues (IM/IC/IF Italy, GR/GF/… Germany as "ME9", US "MDIBF").
- **With exchCode `MTAA`**: HTTP 200, 749 ms, **0 matches** (MIC rejected).
- Best match ticker → **MB** on **IM** → Yahoo `MB.MI`.

### Test 2 — Sanofi `FR0000120578`
- **No exchCode**: HTTP 200, **677 ms**, **142 matches**. First row:
  `{ticker: "SAN", exchCode: "FP", compositeFIGI: BBG000BWBBF3, securityType: "Common Stock"}`.
  Other venues: GR/GY "SNW", US "SNYNF". All share `shareClassFIGI BBG001SCSQN7`.
- **With exchCode `XPAR`**: HTTP 200, 717 ms, **0 matches** (MIC rejected).
- Best match ticker → **SAN** on **FP** → Yahoo `SAN.PA`.

### Test 3 — SAP `DE0007164600`
- **No exchCode**: HTTP 200, **696 ms**, **256 matches**. First row exchCode `SW` (Swiss); German rows ticker **SAP** across GR/GF/GD/GY/GS/GM/GI/GH; US "SAPGF".
- **With exchCode `GY`**: HTTP 200, 759 ms, **1 match** — clean:
  `{figi: BBG000BG7GX2, ticker: "SAP", exchCode: "GY", compositeFIGI: BBG000BG7DY8}` → Yahoo `SAP.DE`.
- Best match ticker → **SAP** → Yahoo `SAP.DE`.

**Latency**: 677–941 ms/request (mean ≈ 720 ms). Batched (100 jobs/request), full 187-deal backfill is ~2 requests + rate-limit waits ≈ under 1 min.

## Field Mapping for Resolver

- **Primary field**: `ticker` (Bloomberg local ticker, e.g. MB / SAN / SAP).
- **Venue**: `exchCode` (Bloomberg) — needed to (a) select the home listing and (b) derive the Yahoo suffix.
- **Identity guard**: `compositeFIGI` / `shareClassFIGI` are constant across a security's venues → confirms all rows are the *same* company. This is the structural reason OpenFIGI avoids the Phase-10 failure mode (yfinance bare-ISIN returned *wrong securities* — Turkey ETF, penny stocks). Here every row is the right issuer; the only task is venue selection, not identity verification.
- **Yahoo suffix mapping** (Bloomberg exchCode → Yahoo suffix), the real Step-1 work:
  `FP→.PA`, `IM→.MI`, `GY→.DE` (and composite `GR→.DE`), plus the others present in our 187-deal corpus (FR/DE/IT dominant). US `US`→ no suffix.

## Recommendations for Step 1

1. **Query strategy — no exchCode, filter client-side.** Always send `{idType: ID_ISIN, idValue: isin}` *without* a hint (it always resolves if the security exists anywhere). Then select the home venue. Hinting with Bloomberg exchCode also works (SAP+GY gave exactly 1 row) but is brittle when the home-venue code is uncertain — keep it as a secondary disambiguator, not the primary call.
2. **Disambiguation rules** (priority order):
   - Map ISIN country prefix → expected Bloomberg exchCode set (`FR→{FP}`, `IT→{IM}`, `DE→{GR,GY}`).
   - Among `data` rows with `securityType == "Common Stock"` and `marketSector == "Equity"`, pick the row whose `exchCode` is in that set; prefer the composite/home row.
   - If none on the home venue, fall back to the first equity row sharing the dominant `compositeFIGI` (still the right issuer) and flag `venue_fallback=true`.
   - Map chosen `exchCode` → Yahoo suffix; emit `ticker + suffix`.
3. **Error handling**: `warning "No identifier found"` → `None` (route to manual_review, no poison). Empty `data` → `None`. Multiple issuers (different `shareClassFIGI`) → ambiguous → `None` + log. HTTP 429 → backoff (respect 25/min).
4. **Cache strategy**: persist ISIN→(ticker, exchCode, figi) in a small SQL table or JSON cache keyed by ISIN; OpenFIGI mappings are stable, so cache indefinitely and only call on cache miss. Mirrors the curated-map philosophy of `target_ticker_resolver` but auto-populated.
5. **Validation gate (Step 2)**: resolving the right *issuer* is necessary but not sufficient — Step 2 must still cross-check the resolved Yahoo ticker's close vs the offer price (the Phase-10 deviation check) before any backfill, to catch suffix-mapping errors and stale/delisted venues.

## Verdict (Step 0)

**GO for Step 1.** 3/3 ISINs resolved to the correct issuer (vs yfinance's 25% real success), no wrong-security false positives, sub-second latency, generous quota. The two open engineering risks — Bloomberg-vs-Yahoo suffix mapping and home-venue selection — are bounded and explicitly gated by the Step 2 deviation checkpoint.
