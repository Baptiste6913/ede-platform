"""P9.2 02b Step 0 — automatic pre-review of the 19 suspect cases.

For every row in ``data/audits/p92_02b_ground_truth.csv`` whose status flags
a likely false positive (any ``mismatch_*`` or ``no_engagement_clause``),
this script:

1. Loads the full PDF text (PyMuPDF, all pages).
2. Captures every plausible price clause: the literal patterns
   ``X € par action`` / ``au prix [unitaire] de X €`` / ``X euros`` —
   each with a 300-char window of surrounding context.
3. Auto-classifies the trap pattern by keyword presence
   (OCEANE/BSA, dividend, surenchère, block-purchase, no-clause).
4. Picks a best-guess "true offer price" based on which candidate sits
   inside the principal commitment clause (``s'engage à acquérir … au
   prix [unitaire] de X €`` with optional ``relevé/modifié`` qualifier).
5. Assigns a HIGH / MEDIUM / LOW confidence so the human reviewer can
   skip the cases the script is sure about.

Writes ``data/audits/p92_02b_pre_review.md`` (markdown, one section per
case + an aggregate summary at the end).

This script does NOT modify the parser. It is exploratory analysis only.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_CSV = REPO_ROOT / "data" / "audits" / "p92_02b_ground_truth.csv"
OUT_MD = REPO_ROOT / "data" / "audits" / "p92_02b_pre_review.md"

# Both ASCII apostrophe (U+0027) and curly U+2019 appear in the corpus.
# We build the character class programmatically so the source file stays
# ASCII-only (ruff RUF001/RUF003 friendly).
_APOS_CLASS = "[" + "'" + chr(0x2019) + "]"

# Principal engagement clause: this is what the parser SHOULD anchor on. The
# 400-char allowance covers the parenthetical inserts AMF uses
# ("au prix unitaire de 38,18 € (dividende attaché)", etc.).
_PRINCIPAL = re.compile(
    "s" + _APOS_CLASS + r"\s*engage\s+(?:\w+\s+){0,3}[àa]\s+acqu[ée]rir"
    r"[\s\S]{0,400}?"
    r"prix\s+(?:unitaire\s+)?(?:relev[ée]\s+)?(?:modifi[ée]\s+)?de\s+"
    r"(?P<amount>\d{1,3}(?:[\s.\xa0]\d{3})*(?:[,.]\d{1,4})?)"
    r"\s*(?:€|euros?)",
    re.IGNORECASE,
)

# Any euro amount with a price-class preposition. Used to enumerate the
# alternatives in the PDF (every candidate the regex could have picked).
_ANY_PRICE = re.compile(
    r"(?P<amount>\d{1,3}(?:[\s.\xa0]\d{3})*(?:[,.]\d{1,4})?)\s*(?:€|euros?)",
    re.IGNORECASE,
)

# Keyword sets per pattern. Searched case-insensitively in the full PDF text.
_PATTERN_KEYWORDS: dict[str, list[str]] = {
    "OCEANE": [
        "OCEANE",
        "océanes",
        "OCÉANE",
        "obligation convertible",
        "obligations convertibles",
        "BSA",
        "bons de souscription",
        "valeur mobilière",
    ],
    "DIVIDEND_TRAP": [
        "cum-dividende",
        "ex-dividende",
        "dividende attaché",
        "dividende détaché",
        "détachement du dividende",
        "détachement de l'acompte",
        "acompte sur dividende",
        "coupon détaché",
        "coupon attaché",
        "dividende exceptionnel",
        "dividende ajusté",
    ],
    "SURENCHERE": [
        "surenchère",
        "surenchere",
        "offre amendée",
        "prix relevé",
        "prix modifié",
        "prix unitaire relevé",
        "prix unitaire modifié",
        "au lieu de",
    ],
    "BLOCK_PURCHASE": [
        "a acquis",
        "a procédé à l'acquisition",
        "hors marché",
        "acquisition de bloc",
        "préalable",
        "cession hors marché",
    ],
}


@dataclass
class PriceCandidate:
    amount: Decimal
    context: str
    is_principal: bool = False


@dataclass
class CaseReview:
    ref: str
    target: str
    status: str
    extracted: Decimal | None
    pattern: str = "UNCLEAR"
    keyword_hits: dict[str, list[str]] = field(default_factory=dict)
    principal_excerpts: list[str] = field(default_factory=list)
    candidates: list[PriceCandidate] = field(default_factory=list)
    best_guess: Decimal | None = None
    confidence: str = "LOW"
    notes: list[str] = field(default_factory=list)


def _normalise_amount(raw: str) -> Decimal | None:
    s = re.sub(r"\s", "", raw).replace(",", ".")
    if s.count(".") > 1:
        head, _, tail = s.rpartition(".")
        s = head.replace(".", "") + "." + tail
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _excerpt(text: str, span: tuple[int, int], *, before: int = 150, after: int = 150) -> str:
    start = max(0, span[0] - before)
    end = min(len(text), span[1] + after)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _local_pdf(stored_path: str) -> Path | None:
    if not stored_path:
        return None
    rel = stored_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


def _read_pdf_text(pdf_path: Path) -> str:
    pieces: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pieces.append(page.get_text("text") or "")
    return "\n".join(pieces)


def _detect_patterns(text: str) -> dict[str, list[str]]:
    """Return ``{pattern_name: [matched_keyword, ...]}`` for every pattern
    whose keyword set hits the text. Multiple patterns may hit at once."""
    hits: dict[str, list[str]] = {}
    lower = text.lower()
    for pattern, keywords in _PATTERN_KEYWORDS.items():
        matched = [kw for kw in keywords if kw.lower() in lower]
        if matched:
            hits[pattern] = matched
    return hits


def _pick_dominant_pattern(hits: dict[str, list[str]], has_principal: bool) -> str:
    if not hits and not has_principal:
        return "NO_CLAUSE"
    # Priority order: a clear OCEANE/BSA marker is the strongest tell because it
    # injects a structurally different price that the bound cannot catch.
    for priority in ("OCEANE", "SURENCHERE", "DIVIDEND_TRAP", "BLOCK_PURCHASE"):
        if priority in hits:
            return priority
    return "UNCLEAR"


def _principal_candidates(text: str) -> list[PriceCandidate]:
    out: list[PriceCandidate] = []
    for m in _PRINCIPAL.finditer(text):
        amount = _normalise_amount(m.group("amount"))
        if amount is None:
            continue
        out.append(
            PriceCandidate(amount=amount, context=_excerpt(text, m.span()), is_principal=True)
        )
    return out


def _all_price_candidates(
    text: str, principal_amounts: set[Decimal], max_count: int = 12
) -> list[PriceCandidate]:
    """Enumerate every '€'-tagged amount in the PDF, deduplicated by value.
    Principal-clause matches are filtered out (caller already has them)."""
    seen: dict[Decimal, PriceCandidate] = {}
    for m in _ANY_PRICE.finditer(text):
        amount = _normalise_amount(m.group("amount"))
        if amount is None or amount in principal_amounts:
            continue
        if amount in seen:
            continue
        seen[amount] = PriceCandidate(amount=amount, context=_excerpt(text, m.span()))
        if len(seen) >= max_count:
            break
    return list(seen.values())


def _best_guess_and_confidence(
    review: CaseReview,
) -> tuple[Decimal | None, str, list[str]]:
    """Heuristic for the true offer price + a HIGH/MEDIUM/LOW confidence."""
    notes: list[str] = []
    principals = [c for c in review.candidates if c.is_principal]

    # Case 1: exactly one principal-clause match → high confidence in that value.
    if len(principals) == 1:
        guess = principals[0].amount
        if review.extracted is not None and review.extracted != guess:
            notes.append(f"Single principal clause has {guess}, parser stored {review.extracted}.")
            return (guess, "HIGH", notes)
        notes.append("Single principal clause agrees with stored value — likely false alarm.")
        return (guess, "HIGH", notes)

    # Case 2: multiple principal-clause matches → surenchère or restated clause.
    if len(principals) > 1:
        unique = {c.amount for c in principals}
        if len(unique) == 1:
            guess = principals[0].amount
            notes.append("Multiple principal clauses, same price — confident.")
            confidence = "HIGH"
        else:
            # The LAST principal clause is typically the relevé/final price.
            guess = principals[-1].amount
            notes.append(
                f"Multiple principal clauses with diverging prices "
                f"{sorted(unique)} — picked the LAST one as the surenchère/final."
            )
            confidence = "MEDIUM"
        return (guess, confidence, notes)

    # Case 3: no principal clause → confidence is LOW unless a single
    # non-principal candidate stands out.
    if len(review.candidates) == 1:
        notes.append("Only one €-amount in the PDF — fallback to it but uncertain.")
        return (review.candidates[0].amount, "MEDIUM", notes)
    if not review.candidates:
        notes.append("No price candidates at all — PDF likely text-extraction-failed.")
        return (None, "LOW", notes)
    notes.append("No principal clause found, multiple candidate prices — needs human read.")
    return (None, "LOW", notes)


def _review_one(row: dict[str, str]) -> CaseReview:
    extracted = _normalise_amount(row.get("stored_price") or row.get("offer_price") or "")
    review = CaseReview(
        ref=row["regulator_ref"],
        target=row["target_name"],
        status=row["status"],
        extracted=extracted,
    )
    pdf = _local_pdf(row.get("pdf_path", ""))
    if pdf is None:
        review.notes.append("PDF not found locally.")
        return review
    try:
        text = _read_pdf_text(pdf)
    except Exception as exc:
        review.notes.append(f"PDF read failed: {type(exc).__name__}: {exc}")
        return review

    review.keyword_hits = _detect_patterns(text)
    principals = _principal_candidates(text)
    review.candidates.extend(principals)
    principal_amounts = {p.amount for p in principals}
    review.candidates.extend(_all_price_candidates(text, principal_amounts))

    # Principal excerpts are useful for the markdown output.
    review.principal_excerpts = [p.context for p in principals]

    review.pattern = _pick_dominant_pattern(review.keyword_hits, has_principal=bool(principals))
    review.best_guess, review.confidence, more_notes = _best_guess_and_confidence(review)
    review.notes.extend(more_notes)
    return review


def _render_case(idx: int, r: CaseReview) -> str:
    lines: list[str] = []
    lines.append(f"## Case {idx} — {r.target} ({r.ref})")
    lines.append("")
    lines.append(f"- **Auto-classified status**: `{r.status}`")
    extracted = f"{r.extracted} €" if r.extracted is not None else "(none)"
    lines.append(f"- **Stored price (parser)**: {extracted}")
    lines.append(f"- **Pattern auto-detected**: `{r.pattern}`")
    lines.append(f"- **Confidence**: `{r.confidence}`")
    best = f"{r.best_guess} €" if r.best_guess is not None else "(unable to guess)"
    lines.append(f"- **Best-guess true price**: {best}")
    lines.append("")

    if r.keyword_hits:
        lines.append("### Keyword hits")
        for pat, kws in r.keyword_hits.items():
            unique = sorted(set(kws))
            lines.append(f"- **{pat}**: {', '.join(repr(k) for k in unique)}")
        lines.append("")

    if r.principal_excerpts:
        lines.append("### Principal engagement clause(s)")
        for i, ex in enumerate(r.principal_excerpts, 1):
            lines.append(f"{i}. `{ex}`")
        lines.append("")
    else:
        lines.append("### Principal engagement clause(s)")
        lines.append("_No `s'engage à acquérir … au prix` clause found in the PDF._")
        lines.append("")

    non_principal = [c for c in r.candidates if not c.is_principal]
    if non_principal:
        max_shown = 8
        lines.append("### Alternative €-amounts in the PDF")
        for c in non_principal[:max_shown]:
            lines.append(f"- **{c.amount} €** — {c.context}")
        if len(non_principal) > max_shown:
            lines.append(f"- ... ({len(non_principal) - max_shown} more truncated)")
        lines.append("")

    if r.notes:
        lines.append("### Notes")
        for n in r.notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("### Recommended verdict for human review")
    lines.append("- [ ] FP confirmed (extracted price ≠ true price)")
    lines.append("- [ ] False alarm (extracted price IS correct)")
    lines.append("- [ ] Cannot determine (PDF issue, ambiguous)")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _suspect(row: dict[str, str]) -> bool:
    st = row["status"]
    return ("mismatch" in st) or (st == "no_engagement_clause")


def main() -> None:  # noqa: PLR0915 — single linear flow, splitting hurts readability
    with GROUND_TRUTH_CSV.open(encoding="utf-8") as fh:
        all_rows = list(csv.DictReader(fh))
    suspects = [r for r in all_rows if _suspect(r)]

    print(f"Reviewing {len(suspects)} suspect cases out of {len(all_rows)} sample deals.")

    reviews: list[CaseReview] = []
    for row in suspects:
        print(f"  - {row['regulator_ref']} {row['target_name'][:32]}")
        reviews.append(_review_one(row))

    # ----- Render markdown -----
    md_lines: list[str] = []
    md_lines.append("# P9.2 02b Step 0 — pre-review of 19 suspect cases\n")
    md_lines.append(
        "Auto-generated by `scripts/p92_02b_pre_review.py`. Every row in "
        "`data/audits/p92_02b_ground_truth.csv` whose auto-classification flagged "
        "a likely false positive (`mismatch_*` or `no_engagement_clause`) is "
        "expanded here with: every €-amount in the PDF + its surrounding context, "
        "an auto-detected trap pattern, a best-guess true price, and a HIGH / "
        "MEDIUM / LOW confidence level. This file is meant to **shortcut the "
        "human review**: spot-check the HIGH-confidence verdicts and focus "
        "attention on the LOW-confidence rows.\n"
    )
    md_lines.append("---\n")
    for i, r in enumerate(reviews, 1):
        md_lines.append(_render_case(i, r))

    # ----- Aggregate summary -----
    pat_counts = Counter(r.pattern for r in reviews)
    conf_counts = Counter(r.confidence for r in reviews)
    fp_high = [r for r in reviews if r.confidence == "HIGH" and r.best_guess != r.extracted]
    falsealarm_high = [r for r in reviews if r.confidence == "HIGH" and r.best_guess == r.extracted]
    low_conf = [r for r in reviews if r.confidence == "LOW"]

    md_lines.append("## Aggregate auto-analysis (to be validated by human)\n")
    md_lines.append("### Patterns detected\n")
    for pat in sorted(pat_counts):
        md_lines.append(f"- **{pat}**: {pat_counts[pat]} / {len(reviews)}")
    md_lines.append("")

    md_lines.append("### Confidence distribution\n")
    for conf in ("HIGH", "MEDIUM", "LOW"):
        md_lines.append(f"- **{conf}**: {conf_counts.get(conf, 0)} / {len(reviews)}")
    md_lines.append("")

    md_lines.append("### Pre-review verdicts (HIGH confidence)\n")
    md_lines.append(f"- **FP confirmed (HIGH)**: {len(fp_high)} cases")
    for r in fp_high:
        md_lines.append(
            f"  - {r.ref} {r.target}: stored `{r.extracted}` "
            f"→ guess `{r.best_guess}` ({r.pattern})"
        )
    md_lines.append(f"- **False alarm (HIGH)**: {len(falsealarm_high)} cases")
    for r in falsealarm_high:
        md_lines.append(f"  - {r.ref} {r.target}: stored `{r.extracted}` likely correct")
    md_lines.append(f"- **LOW confidence (needs human read)**: {len(low_conf)} cases")
    for r in low_conf:
        md_lines.append(f"  - {r.ref} {r.target} ({r.pattern})")
    md_lines.append("")

    md_lines.append("### Refined FP rate estimate (pre-review)\n")
    md_lines.append(
        f"- FP confirmed HIGH-confidence: {len(fp_high)} / {len(reviews)} suspects "
        f"= {100 * len(fp_high) / len(reviews):.1f}% of suspects"
    )
    md_lines.append(
        f"- Cases the script would call 'false alarm' (parser actually right): "
        f"{len(falsealarm_high)} / {len(reviews)}"
    )
    md_lines.append(
        f"- LOW confidence → need human: {len(low_conf)} / {len(reviews)} "
        f"(spend ~{3 * len(low_conf)} min reading those PDFs)"
    )
    md_lines.append("")

    md_lines.append("### Recommended human time budget\n")
    fp_high_threshold = 8  # cutoff at which we trust the auto-classifier to drive the human review
    if len(fp_high) >= fp_high_threshold:
        md_lines.append(
            "- HIGH-confidence FP majority — spot-check 3-5 of them (10 min), "
            "trust the rest. Focus the remaining review time on LOW cases."
        )
    else:
        md_lines.append(
            "- Mixed verdict population — read every LOW + every HIGH that "
            "doesn't match a known pattern (~30 min)."
        )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print()
    print(f"Markdown: {OUT_MD}")
    print(f"  patterns:    {dict(pat_counts)}")
    print(f"  confidences: {dict(conf_counts)}")
    print(f"  FP high:     {len(fp_high)}")
    print(f"  False alarm: {len(falsealarm_high)}")
    print(f"  LOW (human): {len(low_conf)}")


if __name__ == "__main__":
    main()
