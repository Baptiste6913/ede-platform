# P9.1b — scope (draft)

Carried over from P9.1a. Not committed-to yet; **two scope decisions open** (★).

- **Re-score the 6 invalidated deals.** P9.1a cleared scores for Linus, infas,
  DFV, Commerzbank, ProSieben (5 legit) + Klassik (recovered, score cleared by
  the buggy first backfill run). Re-run Phase-6 scoring on the corrected prices.
- **External price validation** of `verified_cash`. Cross-check each anchored
  price against an external quote per ISIN (yfinance / OpenFIGI) → set
  `failed_validation` on mismatches. Turns the audit's magnitude heuristic into
  a real check (catches genuine-but-wrong prices the parser accepted).
- **★ Phase-6 treatment of `suspect_mixed`** (Commerzbank, ProSieben). Decide:
  exclude from scoring/trading entirely, **or** structure the consideration
  (cash_eur + share_ratio + acquirer ISIN), compute economic value via the
  acquirer quote, and include with a reduced/flagged weight. Needs a model
  change (acquirer security + ratio fields, migration 0015).
- **★ The 802 `parser_version = 1` deals.** Batch re-parse the historical corpus
  with v2 to benefit from the Geldleistung/Gegenleistung anchoring + mixed
  detection, **or** keep "v2 = new deals only" and leave history as-is? If batch:
  it's the same backfill pattern, but FR/IT use different parsers (AMF/Consob) —
  the BaFin fix only helps the ~25 non-outlier DE deals; FR/IT need P9.2 first.
