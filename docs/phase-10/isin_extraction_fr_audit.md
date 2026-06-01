# Phase 10 Step 1 — ISIN extraction FR audit

Anchor on the first FR-prefixed ISIN occurring in the first 2 pages of each AMF BDIF PDF. Persisted to `deals.ticker_target` for every FR labelled deal that previously carried no ticker. Idempotent — re-running this script skips deals whose `ticker_target` is already set.

## Summary

- Deals processed : **148**
- ISIN found + applied : **148** (100.0%)
- Skipped : 0

### Status distribution

| Status | Count |
|---|---:|
| `applied` | 148 |
