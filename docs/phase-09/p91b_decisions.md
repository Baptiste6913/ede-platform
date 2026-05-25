# P9.1b — decisions (resolved)

Closes the two open scope questions from `p91b_scope.md`. Driven by a code
audit: `parser_version` and `offer_price_quality_flag` have **zero consumers**
(grep) beyond their definitions, and Phase-6 scoring does **not** use
`offer_price` (features use `premium_pct`, which is NULL on all 819 deals).

## Decision (3) — `suspect_mixed`: excluded from trading, not weighted

A share-exchange / cash+share offer has no reliable scalar price, so it is
**excluded** from the trade loop. Made explicit: `load_candidates` now filters
`offer_price_quality_flag NOT IN UNTRADEABLE_OFFER_PRICE_FLAGS`
(`suspect_mixed`, `failed_validation`, `manual_review`).

Why not "include with reduced weight": scoring is offer_price-agnostic, so a
weight would be an arbitrary hyperparameter polluting the backtest for no signal
gain. Trading mixed offers requires **structuring the consideration** (cash_eur
+ share_ratio + acquirer ISIN, economic value via the acquirer quote) → **P9.1d**.
Until then, exclude. Behaviour-preserving today (mixed already has a NULL price
the decision engine skips); the filter just makes it explicit + future-proofs
the P9.1c `failed_validation` flag.

> Note: the P9.1a backfill deleted the 6 scores of corrected/nulled deals on the
> assumption that the price feeds the score. It does not. Re-generating them
> would return identical `p_completion`, so it is **skipped** (noise for zero
> info). They will be re-created by the next full scoring run.

## Decision (4) — the 802 `parser_version = 1` deals: v2-on-new only

**No batch re-parse.** `parser_version` has no consumer and there is no backtest
needing pre-fix history (grep: no `backtest` module). The column stays an audit
trail: `v2` = re-parsed since 2026-05-25 (the 17 P9.1a outliers); everything
else stays `v1`. FR/IT use different parsers (AMF / Consob) — the BaFin fix does
not help them; that is **P9.2**. If a future backtest needs corrected DE
history, re-parse only the ~25 non-outlier DE deals (the synonym sweep already
shows the v2 parser yields `verified_cash` for them).

## Deferred (not P9.1b)

- **P9.1c** — pricing foundation (stooq/yfinance + OpenFIGI + IBKR fallback;
  cache = the `prices` hypertable). First task: cross-check stooq vs yfinance
  coverage on 10-20 representative DE small-caps before fixing the primary source.
- **P9.1d** — structure mixed offers (unblocks Commerzbank, ProSieben). Builds on
  P9.1c.
- **P9.1e** — populate `premium_pct` + **re-fit** the model + validate AUC/Brier
  vs the `scoring_v1_20260520` baseline (see `docs/scoring/known_issues.md`).
  Builds on P9.1c.
