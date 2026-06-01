# Phase 9.2 02b — Step 0 Final Audit

**Date**: 2026-06-01
**Reviewer**: Baptiste + Claude Code (pre-review automated)
**Branch**: `phase-09-02b-amf-positional-anchoring`

Closes the P9.2 02b Step 0 audit: measures the empirical false-positive
rate of the AMF parser's positional anchoring on the 596 `verified_cash`
corpus, catalogues the trap patterns with nominative examples, and
proposes a per-pattern fix strategy for Step 1. **No parser code
modified at this step.**

## 1. Methodology

| Step | Output | Notes |
|---|---|---|
| Stratified sample (12/year × 5 years + obligatoires) | `data/audits/p92_02b_sample.csv` | 68 deals: 8 obligatory + 60 random. Seed-pinned. Excludes targets already audited in 02a Step 0. |
| Auto-classification (regex heuristic) | `data/audits/p92_02b_ground_truth.csv` | Each row labelled `match` / `mismatch` / `no_engagement_clause` against the stored `offer_price`. |
| Pre-review (Claude Code) | `data/audits/p92_02b_pre_review.md` | The 19 suspects expanded with every €-amount + context + best-guess true price + HIGH/MEDIUM/LOW confidence. |
| Manual review (Baptiste + Claude Code) | `data/audits/p92_02b_manual_review.md` | 3 HIGH spot-checks + per-case verdict on the 7 LOW. |

## 2. Results

### 2.1 Refined FP rate

| Metric | Value |
|---|---|
| Random sample size | 60 deals |
| Confirmed FPs (random only) | 9 |
| **Refined FP rate** | **15.0%** |
| Brut auto-classification rate (Step 0) | 20.0% — gap = 3 false alarms of the pre-review heuristic itself |
| Extrapolation on 596 `verified_cash` | ~90 deals concerned (interval ~75-105 with ±2σ on a 15% point estimate) |

### 2.2 Pattern distribution (14 confirmed FPs)

| Pattern | Count | Share | Mechanism |
|---|---|---|---|
| **BLOCK_PURCHASE** | 6 | 43% | Regex captures a historical block-trade price quoted *before* the engagement clause (`a acquis ... au prix de X`, `par transparence des opérations`). |
| **SURENCHERE** | 4 | 29% | Regex captures the *initial* price quoted in the surenchère filing instead of the raised price (`prix modifié`, `rehaussé`, `visées dorénavant`, `au lieu de`). |
| **DIVIDEND_TRAP** | 3 | 21% | Regex picks the ex-div price when both cum-div and ex-div are mentioned. Convention adopted: cum-div. |
| **OCEANE/BSA** | 1 | 7% | Regex captures the warrant strike or convertible exercise price instead of the share offer price. |

### 2.3 Dataset convention

`offer_price` stores the **cum-dividende** price (the announced offer
price in the principal commitment clause, before any dividend
detachment). Concrete corpus examples:

- SELECTIRENTE 218C2043 → 89 € cum-div stored, 86.80 € ex-div not stored (already documented in 02a closure)
- TESSI 219C0051 → 160 € cum-div stored, 117.30 € ex-div not stored
- LE BELIER 220C4135 → **38.18 €** cum-div is the target value (currently 35.12 stored is a FP)
- GROUPE ETPO 225C1227 → **82.33 €** cum-div is the target value (currently 61 stored is a FP)

Convention to be documented in `docs/PARSER_AMF.md` § Conventions
(creation of that file is itself Step 1 scope, not Step 0).

### 2.4 Confirmed FPs (14)

| Ref | Target | Stored | True | Pattern |
|---|---|---|---|---|
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | 2.85 | BLOCK_PURCHASE |
| 224C1289 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | 2.85 | BLOCK_PURCHASE |
| 218C1907 | SERMA GROUP | 229.19 | 235 | BLOCK_PURCHASE (via `par transparence`) |
| 218C2028 | SERMA GROUP | 229.19 | 235 | BLOCK_PURCHASE (via `a acquis`) |
| 221C1910 | GENKYOTEX | 2.80 | 2.85 | DIVIDEND_TRAP |
| 218C1043 | CFI-COMPAGNIE FONCIERE INTERNATIONALE | 0.83 | 1.00 | SURENCHERE |
| 220C4135 | LE BELIER | 35.12 | 38.18 | DIVIDEND_TRAP |
| 224C1700 | GALIMMO | 9.02 | 14.83 | BLOCK_PURCHASE |
| 224C2193 | NHOA | 1.10 | 1.25 | SURENCHERE |
| 224C1145 | OSMOZIS | 13.50 | 15 | DIVIDEND_TRAP |
| 223C2035 | TECHNICOLOR CREATIVE STUDIOS | 0.01 | 1.63 | OCEANE/BSA |
| 226C0661 | MEDIA 6 | 9.69 | 9.89 | SURENCHERE |
| 226C0645 | MEDIA 6 | 9.69 | 9.89 | SURENCHERE |
| 225C1227 | GROUPE ETPO SA | 61.00 | 82.33 | DIVIDEND_TRAP + BLOCK_PURCHASE |

### 2.5 False alarms (3) — parser was correct

| Ref | Target | Stored | True | Reason for flag |
|---|---|---|---|---|
| 226C0550 | TERACT | 3.12 | 3.12 ✓ | Multi-bullet formulation `au prix de :\n- 3,12 € par action` not matched by the pre-review regex |
| 226C0157 | TERACT | 3.12 | 3.12 ✓ | Same multi-bullet pattern as 226C0550 |
| 224C1861 | NHOA | 1.25 | 1.25 ✓ | `visées dorénavant au prix unitaire de 1,25 €` formulation not matched by the pre-review regex |

These three cases tell the parser team that the **Step 1 anchor must
match multi-bullet and surenchère phrasings** to avoid losing the 3
currently-correct extractions when the new logic ships.

## 3. Recommended fix strategy for Step 1

### 3.1 BLOCK_PURCHASE — priority 1 (43% of FPs)

**Root cause**. The current regex matches the first €-tagged amount in
the text and stops; on filings where prior block trades are recapped
before the engagement clause (which is the norm on retraits
obligatoires and surenchères), the recap price wins.

**Fix strategy**.

1. Anchor the price extraction on the principal commitment verb:
   `s'engage\s+(irrévocablement\s+)?à\s+acquérir.*?prix\s+(unitaire\s+)?(modifi[ée]\s+|relev[ée]\s+)?de\s+(<amount>)\s*€`.
2. When the regex returns multiple matches (surenchère restated below),
   prefer the last (final-state) match.
3. Fallback to the current first-match regex only when the anchored
   form returns nothing → covers the multi-bullet edge cases.

**Keywords to add to the BLOCK_PURCHASE catalogue** (used by the
pre-review tooling, not by the parser):

- `par transparence`
- `opérations intervenues`
- `ressortant des opérations`
- `ressortant par transparence`

### 3.2 SURENCHERE — priority 2 (29% of FPs)

**Root cause**. Surenchère filings restate the original price *before*
the raised one. First-match regex captures the original.

**Fix strategy**.

1. Detect surenchère keywords in the PDF body: `prix modifié`, `prix
   relevé`, `rehaussé`, `visées dorénavant`, `au lieu de`.
2. When detected, switch to the LAST occurrence of the anchored
   engagement clause (item 3.1.2 above).
3. Edge case: MEDIA 6 226C0661 / 226C0645 — the engagement verb is
   absent and the phrasing is `prix d'offre … rehaussé au prix de 9,89
   €`. Add a fallback anchor: `prix\s+(d['']offre\s+)?(libellé\s+)?(initialement\s+)?rehauss[ée]\s+au\s+prix\s+de\s+(<amount>)\s*€`.

**Keywords to add to the SURENCHERE catalogue**:

- `rehaussé`
- `visées dorénavant`
- `au lieu de`
- `libellé initialement`

### 3.3 DIVIDEND_TRAP — priority 3 (21% of FPs)

**Root cause**. PDFs with a coupon detachment between announcement and
opening quote both cum-div and ex-div prices. The regex picks whichever
appears first.

**Fix strategy** — **convention: store the cum-dividende price**.

1. When both prices appear (typically `X € (dividende attaché)` and
   `Y € (dividende détaché)`), prefer the one with `(dividende
   attaché)` qualifier.
2. Heuristic backup: when ambiguous, prefer the HIGHER of the two
   amounts (cum-div is by definition ≥ ex-div).

**Keywords to add to the DIVIDEND_TRAP catalogue**:

- `dividende attaché`
- `dividende détaché`
- `acompte sur dividende`
- `ex-coupon`
- `cum-coupon`

### 3.4 OCEANE/BSA — priority 4 (7% of FPs)

**Root cause**. The same PDF carries both the share price and the
warrant/OCEANE exercise price (typically 0.01–10 €). The regex picks
the first match, which is often the strike.

**Fix strategy**.

1. When OCEANE/BSA/BSAR keywords are present in the PDF, require the
   chosen price to be qualified by `par action <TARGET>` (literal
   target name from the deal metadata) or `par action` plus an absence
   of `par BSAR` / `par BSA` / `par bon` within 30 chars.
2. The bound `[0.01, 100000]` already filters extreme outliers
   correctly; the issue is anchoring, not range.

### 3.5 Multi-bullet formulation — priority 5 (covers 2 of the 3 false alarms)

**Root cause**. AMF templates introduce multi-leg offers with a
literal bullet list: `L'initiateur s'engage à acquérir au prix de :\n-
3,12 € par action TERACT\n- 0,0039 € par BSAR B`.

**Fix strategy**. Extend the anchored regex (3.1.1) to allow `:` and a
line break between the verb and the amount:

```
prix\s+(unitaire\s+)?de\s*[:\-]?\s*(?:\n\s*-\s*)?(<amount>)\s*€
```

Or run a second pass when the primary regex returns zero and the
keyword set hits OCEANE → search for `(?:au\s+prix\s+de\s*:\s*\n\s*-?\s*)(<amount>)\s*€\s+par\s+action`.

## 4. Tech debt — none acted

The TECHNICOLOR `offer_price = 0.01` case was investigated as a
candidate `PRICE_LOWER_AMF` fallback bug. **Verdict: not a bug.** The
service writes `0.01` because the parser legitimately extracts that
amount from the PDF (warrant strike) and the bound check uses `<` not
`<=`, so 0.01 exactly passes. It is a positional-anchoring FP, same
class as the other 13.

## 5. Files generated by this audit

| Path | Status | Tracked? |
|---|---|---|
| `data/audits/p92_02b_sample.csv` | committed | gitignored |
| `data/audits/p92_02b_ground_truth.csv` | committed | gitignored |
| `data/audits/p92_02b_pre_review.md` | committed | gitignored |
| `data/audits/p92_02b_manual_review.md` | committed | gitignored |
| `data/audits/p92_02b_final_review.md` | committed | gitignored |
| `scripts/p92_02b_sample.py` | committed | tracked |
| `scripts/p92_02b_ground_truth.py` | committed | tracked |
| `scripts/p92_02b_pre_review.py` | committed | tracked |

`docs/phase-09/p92_02b_final_review.md` is the same content as the
`data/audits/` copy — kept under `data/audits/` so the audit trail
travels with the CSVs.

## 6. Next steps

- **Step 1**: implement the per-pattern fix strategy above on
  `src/ingestion/amf/parser.py`, with regression tests on every
  confirmed FP + every false alarm + a 60-deal random sample re-run.
- **Backfill 02b**: re-parse the 596 `verified_cash` rows on
  `parser_version=3` and invalidate `scores` for the changed rows.
- **Closure 02b**: when Step 1 ships, expect the FP rate to drop from
  15% to ≤2% (target). Re-run this audit on a fresh 60-deal sample to
  confirm.

Step 1 is **not** triggered by this commit — Step 0 stops here.
