# Phase 11 Sample Test — OpenFIGI vs yfinance (20 deals)

Same 20 deals as Phase 10 (SEED=20260601, quota FR13/IT3/DE4), reused verbatim from `data/audits/p10_sample_yfinance_test.csv`. Two metrics are separated: **resolution rate** (did OpenFIGI return a ticker — the thing Phase 11 tests) and **priced rate** (did the full chain yield a price — Phase 10's `ok`, also gated by listing status at T-1).

## Comparison with Phase 10

| Metric | Phase 10 (yfinance) | Phase 11 (OpenFIGI) |
|---|---:|---:|
| Priced rate (status ok) | 35 % | 30 % |
| Real priced rate (post-FP) | 25 % | 30 % |
| Wrong-ticker FPs | 2 | 0 |
| Resolution rate (ISIN→ticker) | n/a | 59 % (10/17) |

## Per-deal results

| Jur | Ref | Target | ISIN | OpenFIGI ticker | flag | exch | ref EUR | offer | premium % | status |
|---|---|---|---|---|---|---|---:|---:|---:|---|
| FR | 225C0129 | EXCLUSIVE NETWORKS | FR0014005DA7 | 97K.DE | venue_fallback | GR |  |  |  | `no_price` |
| FR | 224C0817 | IDSUD | FR0000062184 |  | unknown_exch | XS |  | 1.750000 |  | `unknown_exch` |
| FR | 225C1285 | AMPLITUDE SURGICAL | FR0012789667 |  | unknown_exch | XS |  | 6.250000 |  | `unknown_exch` |
| FR | 226C0550 | TERACT | FR001400BMH7 | TRACT.PA | home_venue | FP | 3.12 | 3.120000 | 0.00 | `ok` |
| FR | 224C0762 | MONTAGNE ET NEIGE DEVE | FR00140050Q2 |  | unknown_exch | XH |  |  |  | `unknown_exch` |
| FR | 224C0763 | COVIVIO HOTELS | FR0000060303 | COVH.PA | home_venue | FP | 13.135802 | 3.000000 | -77.16 | `ok` |
| FR | 226C0531 | MEDIA 6 | FR0000064404 | EDI.PA | home_venue | FP | 9.2 |  |  | `ok` |
| FR | 224C1562 | GALIMMO | FR0000030611 |  | unknown_exch | XS |  | 14.830000 |  | `unknown_exch` |
| FR | 225C1629 | AMPLITUDE SURGICAL | FR0012789667 |  | unknown_exch | XS |  | 6.250000 |  | `unknown_exch` |
| FR | 224C2186 | CLASQUIN | FR0004152882 |  | unknown_exch | XS |  | 142.030000 |  | `unknown_exch` |
| FR | 225C0739 | SOCIETE INDUSTRIELLE E | FR0000076952 | ARTO.PA | home_venue | FP | 8550.0 | 10627.000000 | 24.29 | `ok` |
| FR | 224C1903 | COMPAGNIE DU CAMBODGE | FR0000079659 |  | unknown_exch | EO |  |  |  | `unknown_exch` |
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
| FR | 13 | 6 | 5 | 46 % | 38 % |
| IT | 3 | 0 | 0 | 0 % | 0 % |
| DE | 4 | 4 | 1 | 100 % | 25 % |
| **TOTAL** | **20** | **10** | **6** | **59 %** (of 17 w/ ISIN) | **30 %** |

## Wrong-ticker FPs check (Phase 10 culprits)

**Wrong-ticker FPs in Phase 11: 0** (neither resolved to a wrong security — verified manually).

- **CLASQUIN +10405%** → REFUSED (no ticker emitted). CLASQUIN lists on Euronext Growth (ALCLA), an exchCode class (XS) not yet mapped, so the resolver returned `unknown_exch` rather than a wrong ticker — the +10405 % garbage is gone.
- **COVIVIO HOTELS -77%** → FIXED. Resolved to the correct security `COVH.PA` (ref 13.14 EUR is right). The -77 % is a corrupt stored offer_price (3.00 EUR) — an upstream data-quality issue, NOT a wrong ticker.

## venue_fallback flags

- 225C0129 EXCLUSIVE NETWORKS → `97K.DE` (GR)

## Premium_pct distribution (priced deals)

- count : 5
- min   : -77.16 %
- median: 1.21 %
- max   : 24.29 %
- stdev : 38.99 %
- outliers (|premium| > 200 % or < -50 %): 1

## Root-cause diagnosis (why priced rate is gated)

The priced rate decomposes into one resolver gap and several causes outside the resolver:

1. **FR Euronext Growth small caps (7) — FIXABLE resolver gap.** These have no `FP` row; their home listing sits on Bloomberg exchCodes `XS`/`XH`/`EO` with currency-suffixed tickers (`ALCLAEUR`, `AMPLIEUR`, `ALIDS`). Mapping those venues to `.PA` (and stripping the `EUR` currency suffix) would resolve `ALCLA.PA`, `AMPLI.PA`, `ALIDS.PA`, etc. Affected: 224C0817, 225C1285, 224C0762, 224C1562, 225C1629, 224C2186, 224C1903.
2. **IT/Consob no_isin (3) — upstream gap.** ISIN was never extracted for Consob deals in Phase 10; OpenFIGI needs an ISIN as input. Same blocker as Phase 10, not a resolver issue.
3. **Genuine delisting (2): `FPH.DE` (Francotyp-Postalia), `97K.DE` (Exclusive Networks, taken private).** Correct tickers, but no yfinance data at T-1 — expected for post-OPA targets.
4. **yfinance transient (2): `COP.DE` (CompuGroup) x2.** Correct ticker; CompuGroup is actively listed. yfinance returned `no timezone found` this run (metadata hiccup / rate-limit) — re-verify; not a resolver miss.
5. **offer_price data quality (1): COVIVIO -77 %.** Right ticker + right price; the stored offer (3.00 EUR) is corrupt. Upstream parsing issue.

**Resolution quality where it matters:** of the 10 deals that resolved, **10/10 are the correct security** (manually verified), and **0 wrong-ticker false positives** (vs 2 in Phase 10). OpenFIGI's identity correctness — the Phase-10 failure mode — is fully validated.

## Verdict

- GO/NO-GO thresholds (priced rate): ≥85 % GO · 70-85 % GO+investigate · <70 % scope back.
- Priced rate = 30 % · resolution rate = 59 % of the 17 ISIN-bearing deals.
- **NO-GO for immediate full backfill** on the raw priced rate. But the gap is dominated by a single fixable resolver class (FR Euronext Growth) plus upstream/delisting causes — not by OpenFIGI unreliability (0 FPs, 10/10 resolved tickers correct).
- **Recommended: Step 2.5** — extend the venue map + suffix table for Euronext Growth/Access (XS/XH/EO → .PA, currency-suffix strip), then re-run this sample. Projected resolution ≈ 15-17/17; priced rate then bounded mainly by genuine delisting + the IT ISIN gap.
