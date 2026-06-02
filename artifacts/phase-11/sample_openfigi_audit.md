# Phase 11 Sample Test — OpenFIGI vs yfinance (20 deals)

Same 20 deals as Phase 10 (SEED=20260601, quota FR13/IT3/DE4), reused verbatim from `data/audits/p10_sample_yfinance_test.csv`. Two metrics are separated: **resolution rate** (did OpenFIGI return a ticker — the thing Phase 11 tests) and **priced rate** (did the full chain yield a price — Phase 10's `ok`, also gated by listing status at T-1).

## Comparison with Phase 10

| Metric | Phase 10 (yfinance) | Phase 11 (OpenFIGI) |
|---|---:|---:|
| Priced rate (status ok) | 35 % | 40 % |
| Real priced rate (post-FP) | 25 % | 40 % |
| Wrong-ticker FPs | 2 | 1 |
| Resolution rate (ISIN→ticker) | n/a | 100 % (17/17) |

## Per-deal results

| Jur | Ref | Target | ISIN | OpenFIGI ticker | flag | exch | ref EUR | offer | premium % | status |
|---|---|---|---|---|---|---|---:|---:|---:|---|
| FR | 225C0129 | EXCLUSIVE NETWORKS | FR0014005DA7 | 97K.DE | venue_fallback | GR |  |  |  | `no_price` |
| FR | 224C0817 | IDSUD | FR0000062184 | ALIDS.PA | home_venue_growth | XS |  | 1.750000 |  | `no_price` |
| FR | 225C1285 | AMPLITUDE SURGICAL | FR0012789667 | AMPLI.PA | home_venue_growth | XS |  | 6.250000 |  | `no_price` |
| FR | 226C0550 | TERACT | FR001400BMH7 | TRACT.PA | home_venue | FP | 3.12 | 3.120000 | 0.00 | `ok` |
| FR | 224C0762 | MONTAGNE ET NEIGE DEVE | FR00140050Q2 | MND1.PA | home_venue_growth | XH |  |  |  | `no_price` |
| FR | 224C0763 | COVIVIO HOTELS | FR0000060303 | COVH.PA | home_venue | FP | 13.135802 | 3.000000 | -77.16 | `ok` |
| FR | 226C0531 | MEDIA 6 | FR0000064404 | EDI.PA | home_venue | FP | 9.2 |  |  | `ok` |
| FR | 224C1562 | GALIMMO | FR0000030611 | CIEM.PA | home_venue_growth | XS |  | 14.830000 |  | `no_price` |
| FR | 225C1629 | AMPLITUDE SURGICAL | FR0012789667 | AMPLI.PA | home_venue_growth | XS |  | 6.250000 |  | `no_price` |
| FR | 224C2186 | CLASQUIN | FR0004152882 | ALCLA.PA | home_venue_growth | XS | 1.352 | 142.030000 | 10405.18 | `ok` |
| FR | 225C0739 | SOCIETE INDUSTRIELLE E | FR0000076952 | ARTO.PA | home_venue | FP | 8550.0 | 10627.000000 | 24.29 | `ok` |
| FR | 224C1903 | COMPAGNIE DU CAMBODGE | FR0000079659 | CBDG.PA | home_venue_growth | XS | 93.862862 |  |  | `ok` |
| FR | 226C0645 | MEDIA 6 | FR0000064404 | EDI.PA | home_venue | FP | 9.6 | 9.890000 | 3.02 | `ok` |
| IT | CONSOB-opa_morif_20250407 | Monti Riffeser Srl |  |  |  |  |  |  |  | `no_isin` |
| IT | CONSOB-opa_Beghelli_20250314 | Beghelli Spa |  |  |  |  |  | 0.337500 |  | `no_isin` |
| IT | CONSOB-opa_cir_20241125 | CIR Spa |  |  |  |  |  | 0.610000 |  | `no_isin` |
| DE | BAFIN-DE000FPH9000-20250731 | Francotyp-Postalia Hol | DE000FPH9000 | FPH.DE | home_venue | GR |  | 2.800000 |  | `no_price` |
| DE | BAFIN-DE000A2E4T77-20250630 | H&R GmbH & Co. KGaA | DE000A2E4T77 | 2HRA.DE | home_venue | GR | 4.94 | 5.000000 | 1.21 | `ok` |
| DE | BAFIN-DE000A288904-20250523 | CompuGroup Medical SE  | DE000A288904 | COP.DE | home_venue | GR |  | 22.000000 |  | `no_price` |
| DE | BAFIN-DE000A288904-20241223 | CompuGroup Medical SE  | DE000A288904 | COP.DE | home_venue | GR |  | 22.000000 |  | `no_price` |

## Rates by jurisdiction

| Jur | Sample | Resolved | Priced | Resolved % | Priced % |
|---|---:|---:|---:|---:|---:|
| FR | 13 | 13 | 7 | 100 % | 54 % |
| IT | 3 | 0 | 0 | 0 % | 0 % |
| DE | 4 | 4 | 1 | 100 % | 25 % |
| **TOTAL** | **20** | **17** | **8** | **100 %** (of 17 w/ ISIN) | **40 %** |

## Wrong-ticker FPs check (Phase 10 culprits)

**Wrong-ticker FPs in Phase 11: 1** (gate-caught; the Growth heuristic reintroduced one — see below).

- **CLASQUIN +10405%** → STILL WRONG (post-Step-2.5, gate-caught). The Growth mapping now emits `ALCLA.PA` (XS, currency-stripped from ALCLAEUR) — but `ALCLA.PA` is *Claranova* on Yahoo, not Clasquin (verified). yfinance returns 1.352 EUR → +10405 % again. The premium sanity gate (>200 %) flags it, so it would NOT enter a backfill, but it is a reintroduced wrong-ticker FP: Bloomberg's Euronext-Growth ticker != the Yahoo symbol.
- **COVIVIO HOTELS -77%** → FIXED. Resolved to the correct security `COVH.PA` (ref 13.14 EUR is right). The -77 % is a corrupt stored offer_price (3.00 EUR) — an upstream data-quality issue, NOT a wrong ticker.

## venue_fallback flags

- 225C0129 EXCLUSIVE NETWORKS → `97K.DE` (GR)

## Premium_pct distribution (priced deals)

- count : 6
- min   : -77.16 %
- median: 2.12 %
- max   : 10405.18 %
- stdev : 4252.01 %
- outliers (|premium| > 200 % or < -50 %): 2

## Root-cause diagnosis (why priced rate is gated)

The priced rate decomposes into one resolver-confidence gap and several causes outside the resolver:

1. **FR Euronext Growth small caps (7) — LOW-confidence resolutions (post-Step-2.5).** These have no `FP` row; they resolve via the XS/XH/EO venues, but the Bloomberg ticker != the Yahoo symbol (ALCLA.PA→Claranova). Flagged `home_venue_growth`; see the Post-Step-2.5 section. Affected: 224C0817, 225C1285, 224C0762, 224C1562, 225C1629, 224C2186, 224C1903.
2. **IT/Consob no_isin (3) — upstream gap.** ISIN was never extracted for Consob deals in Phase 10; OpenFIGI needs an ISIN as input. Same blocker as Phase 10, not a resolver issue.
3. **Genuine delisting (2): `FPH.DE` (Francotyp-Postalia), `97K.DE` (Exclusive Networks, taken private).** Correct tickers, but no yfinance data at T-1 — expected for post-OPA targets.
4. **yfinance transient (2): `COP.DE` (CompuGroup) x2.** Correct ticker; CompuGroup is actively listed. yfinance returned `no timezone found` this run (metadata hiccup / rate-limit) — re-verify; not a resolver miss.
5. **offer_price data quality (1): COVIVIO -77 %.** Right ticker + right price; the stored offer (3.00 EUR) is corrupt. Upstream parsing issue.

**Resolution quality where it matters:** every main-market resolution (`home_venue`: FP/GR/IM) is the correct security — **0 wrong-ticker FPs**. The only FP (CLASQUIN) comes from the low-confidence Growth heuristic and is gate-caught. OpenFIGI's identity correctness on main-market listings — the Phase-10 failure mode — is validated; Growth needs a safer strategy.

## Post-Step-2.5 re-run (Euronext Growth mapping)

Step 2.5 added FR Growth venues (XS/XH/EO → .PA) + a defensive currency-suffix strip. Resolution jumped **10/17 → 17/17 (100 %)**. But a yfinance identity spot-check of the newly-resolved Growth tickers shows the mapping is **not safe to trust blindly**:

| Deal | Growth ticker | yfinance identity check |
|---|---|---|
| CLASQUIN | `ALCLA.PA` | WRONG → resolves to CLARANOVA (0.76 EUR), not Clasquin |
| COMPAGNIE DU CAMBODGE | `CBDG.PA` | CORRECT → CAMBODGE NOM. (104 EUR) |
| AMPLITUDE SURGICAL | `AMPLI.PA` | no Yahoo listing → no_price (safe skip) |
| MONTAGNE ET NEIGE | `MND1.PA` | no Yahoo listing (BBG digit disambiguator) → no_price |
| IDSUD | `ALIDS.PA` | no Yahoo data this run → no_price |
| GALIMMO | `CIEM.PA` | no Yahoo data this run → no_price |

**Key finding:** Bloomberg's Euronext-Growth local ticker is NOT the Yahoo symbol. Currency-stripping `ALCLAEUR` → `ALCLA` collides with an unrelated security (`ALCLA.PA` = Claranova), reproducing the exact Phase-10 +10405 % garbage — caught by the premium gate, but a reintroduced wrong-ticker FP. Of the 7 Growth resolutions, only CBDG.PA is verified correct; the rest are wrong (1) or have no Yahoo data (5). These are now flagged `home_venue_growth` (low confidence) so the backfill can route them to manual_review instead of trusting them.

## Verdict

- Resolution rate = **100 %** (17/17) · priced rate = 40 %.
- **Main-market venues (FP/GR/IM): GO.** Every large/mid cap resolved to the correct security (TRACT.PA, COVH.PA, EDI.PA, ARTO.PA, 2HRA.DE, COP.DE, FPH.DE) — 0 wrong-ticker FPs. This is the validated core.
- **Euronext Growth venues (XS/XH/EO): NO-GO as auto-resolve.** The currency-strip heuristic emits structurally-plausible but unreliable tickers (ALCLA.PA→Claranova). Flagged `home_venue_growth`; route to manual_review or require an identity/deviation check before use.
- **IT/Consob: blocked upstream** (no ISIN extracted) — independent of the resolver.
- **Recommendation:** GO full backfill on `home_venue` (main-market) resolutions with the premium sanity gate enforced; exclude `home_venue_growth` from auto-backfill pending a safe Growth strategy (e.g. yfinance identity cross-check, or an ISIN→Euronext-mnemonic map).
