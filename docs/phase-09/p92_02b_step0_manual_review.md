# P9.2 02b Step 0 — manual review session log

Interactive review session run on top of the auto-generated
`p92_02b_pre_review.md`. The pre-review pre-classified the 19 suspects
into 10 HIGH / 2 MEDIUM / 7 LOW confidence buckets and named a
best-guess true price for each. The session below records the human
verdicts (Baptiste + Claude Code).

## Session flow

1. **Spot-check HIGH** — 3 cases sampled (SERMA 218C2028, GALIMMO,
   CFI). All 3 confirmed BLOCK_PURCHASE / SURENCHERE patterns as
   pre-classified → the 10 HIGH bucket is trusted as a whole.
2. **Targeted review LOW** — all 7 LOW cases inspected by reading the
   PDF text excerpts the script captured + cross-checking against the
   alternative € amounts.
3. **Targeted investigation** — TECHNICOLOR `offer_price = 0.01` and
   the SERMA UNCLEAR pattern label.

## Spot-check HIGH (3 cases)

| # | Ref | Target | Pre-review verdict | Human verdict | Notes |
|---|---|---|---|---|---|
| 1 | 218C2028 | SERMA GROUP | FP, BLOCK_PURCHASE, 229.19 → 235 | **Confirmed** | 3 "prix par action ... par transparence des opérations" precede the engagement clause at 235 € |
| 2 | 224C1700 | GALIMMO | FP, BLOCK_PURCHASE, 9.02 → 14.83 | **Confirmed** | 2 prior block trades (9.02 Louis Delhaize + 11.93 Primonial Capimmo) before the 14.83 OPAS clause |
| 3 | 218C1043 | CFI | FP, SURENCHERE, 0.83 → 1.00 | **Confirmed** | Hybrid pattern: initial block at 0.83 + "prix modifié de 1,00 €" (surenchère) |

→ HIGH bucket validated. The remaining 7 HIGH cases (TRAVEL TECH ×2,
SERMA 218C1907, GENKYOTEX, LE BELIER, NHOA 224C2193, OSMOZIS) accepted
on the pattern alone without per-case read.

## Targeted review LOW (7 cases)

| # | Ref | Target | Pre-review pattern | **Final verdict** | True price | Pattern (refined) |
|---|---|---|---|---|---|---|
| 1 | 223C2035 | TECHNICOLOR CREATIVE STUDIOS | OCEANE | **FP confirmed** | 1.63 € | OCEANE/BSA — 0.01 € is the warrant strike, 1.63 € is `s'engagent à acquérir au prix unitaire de 1,63 €` |
| 2 | 226C0550 | TERACT | OCEANE | **FALSE ALARM** | 3.12 € (stored value is correct) | Multi-bullet `au prix de :\n- 3,12 € par action` not matched by my pre-review regex |
| 3 | 226C0661 | MEDIA 6 | NO_CLAUSE | **FP confirmed** | 9.89 € | SURENCHERE — "rehaussé au prix de 9,89 €" not in keyword set |
| 4 | 226C0645 | MEDIA 6 | NO_CLAUSE | **FP confirmed** | 9.89 € | Same SURENCHERE pattern as 226C0661 |
| 5 | 225C1227 | GROUPE ETPO SA | DIVIDEND_TRAP | **FP confirmed** | 82.33 € (cum-div) | Compound: 61 € is a prior OPAS reference price (BLOCK_PURCHASE) AND 71 € is the ex-div alternate (DIVIDEND_TRAP). Cum-div convention picks 82.33 |
| 6 | 224C1861 | NHOA | SURENCHERE | **FALSE ALARM** | 1.25 € (stored value is correct) | "visées dorénavant au prix unitaire de 1,25 €" formulation not matched by my pre-review regex |
| 7 | 226C0157 | TERACT | OCEANE | **FALSE ALARM** | 3.12 € (stored value is correct) | Multi-bullet, same shape as 226C0550 |

→ **4 confirmed FPs** + **3 false alarms** in the LOW bucket.

## Targeted investigation 1 — TECHNICOLOR `offer_price = 0.01`

**Question**: is `0.01` exactly equal to `PRICE_LOWER_AMF` a fallback /
sentinel value written by the service when extraction fails?

**Answer**: **No, not a bug.**

- DB query: only 1 FR deal sits at exactly `offer_price = 0.01` in the
  596 verified_cash population (TECHNICOLOR 223C2035 itself).
- `src/ingestion/amf/service.py:86` uses `if md.offer_price <
  PRICE_LOWER_AMF` (strict `<`), so 0.01 exactly passes the bound check
  → does not get rewritten to a sentinel. The value comes straight from
  the parser regex, which legitimately extracted `"au prix unitaire de
  0,01 €"` from the PDF.
- The 0.01 in the PDF is the **BSA exercise price** ("donnant droit à
  un nombre maximum de 1 520 864 actions TECHNICOLOR CREATIVE STUDIOS,
  au prix unitaire de 0,01 €"). The real offer price is **1.63 €** in
  a later sentence the regex did not anchor on.

**Conclusion**: TECHNICOLOR is a standard positional-anchoring FP
(OCEANE/BSA class), not a separate tech debt. Will be corrected by the
Step 1 anchoring fix along with the other 13.

## Targeted investigation 2 — SERMA UNCLEAR pattern label

**Question**: why did SERMA 218C1907 land as pattern `UNCLEAR` while
218C2028 (same deal class) landed as `BLOCK_PURCHASE`?

**Answer**: keyword-set gap.

- 218C2028 contains the literal substring `"a acquis"` → BLOCK_PURCHASE
  keyword hits.
- 218C1907 uses a different formulation:
  `"le prix par action SERMA GROUP ressortant par transparence des
  opérations intervenues, le 12 septembre 2018, est de 229,19 €"` —
  the verb `"a acquis"` does NOT appear, only `"opérations
  intervenues"` and `"ressortant par transparence"`.

**Conclusion**: not a verdict gap (both correctly flagged HIGH FP via
the principal-clause anchor), but the **BLOCK_PURCHASE keyword set
needs to be expanded** for Step 1 — see "Recommended fix strategy"
in `p92_02b_final_review.md`.

## Outcome

- **9 of 60** random sample deals → confirmed FP = **15.0% refined rate**
  (vs. 20% brut Step 0 auto-classification).
- **4 of 8** obligatory cases → confirmed FP (TRAVEL TECH ×2, SERMA
  ×2). The other 4 obligatory cases (the other two SERMA filings + the
  two FNAC DARTY filings already flagged in 02a closure) were already
  documented in `docs/phase-09/p92_02a_closure_summary.md`.
- **14 total FPs** observed across the 68-deal sample.
- **3 false alarms** of the pre-review heuristic — useful guidance for
  the Step 1 fix regex (multi-bullet + `visées dorénavant` cases must
  be matched by the new anchor).

Detailed pattern catalogue, extrapolation to the 596 verified_cash
population, and Step 1 fix strategy live in
`data/audits/p92_02b_final_review.md`.
