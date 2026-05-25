# Scoring — known issues

## `premium_pct` is a dead feature (always NaN)

`deals.premium_pct` is **NULL on all 819 deals** (no ingestion path populates it
— grep: it is only ever *read*, in `src/scoring/features.py`). So the
`bid_premium_pct` feature is always NaN, and the baseline model
`scoring_v1_20260520T141111Z` was trained with it constant — i.e. it learned to
**ignore** the column.

**Impact:** the bid premium — arguably *the* core merger-arb signal — currently
contributes nothing to `p_completion`.

**Fix is not "populate the column" (P9.1e):** filling `premium_pct` is necessary
but not sufficient. Because the baseline learned the feature is signal-free,
activating it requires:
1. populate `premium_pct` (offer price vs pre-announcement reference price —
   needs the P9.1c pricing foundation),
2. **re-fit** the model,
3. **validate** AUC / Brier vs the `scoring_v1_20260520` baseline before adopting.

Until then, treat scoring as not using the premium. Discovered during P9.1b
(see `docs/phase-09/p91b_decisions.md`).
