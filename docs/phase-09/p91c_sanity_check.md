# P9.1c-[G-2.5] — sanity check on the `1/222 offer_price_total_eur` surprise

Pre-flight diagnostic before [G-3] re-fit, to confirm the singleton
`offer_price_total_eur` count in the labelled set (`p91c_scoring_features_audit.md`
§ 3) is not a P9.1c backfill bug.

## Verdict — **OK, expected state.**

The 2 `verified_mixed` deals are:

| id | target | status | completion_label | offer_price | offer_price_total_eur |
|--:|---|---|--:|--:|--:|
| 348 | COMMERZBANK Aktiengesellschaft | announced | **NULL** | NULL | 31.0691 |
| 1059 | ProSiebenSat.1 Media SE | announced | 1 | NULL | 5.6423 |

→ Commerzbank is genuinely a live deal (UniCredit / Commerzbank, OPA
announced 2026-05-05) — it has no `completion_label` yet because it has not
resolved. ProSieben is the labelled one (closed, label = 1).

Hence the 1/222 count in the labelled audit is correct:
**1 verified_mixed labelled (ProSieben) + 0 verified_cash with
`offer_price_total_eur`** (cash deals don't carry that column).

## Cross-check on verified_cash labelled (29)

`Diagnostic A` returned 30 verified_* labelled rows: 29 verified_cash
(`pricing_source = 'parser_only'`, `offer_price_total_eur = NULL`, all DE)
+ 1 verified_mixed (ProSieben, `pricing_source = 'yfinance_enriched'`).

The 29 cash all have `offer_price IS NOT NULL` (the flag guarantees it).
None has `offer_price_total_eur` populated — expected, since the column is
only computed by the P9.1c-[E] recalc for mixed offers. Math:
30 verified_* labelled = 39 DE labelled − 9 manual_review. ✓

## Residual debt noted (out of [G] scope)

`Deal.status = 'announced'` on the 29 verified_cash labelled deals despite
their `completion_label = 1` (closed). The `status` column is not refreshed
when the label is applied via the external labelling process. Not blocking
for the re-fit; to track for P9.1e / P10 backtest hygiene.

## Conclusion

No backfill bug. Cleared to launch [G-3] token re-fit. The expected
prediction stands: ΔBrier ≈ 0, ΔAUC ≈ 0 on the 213-deal test set
(222 labelled − 9 DE manual_review).
