"""P9.2 02b Step 0 — auto-classify ground truth for the 68-deal sample.

Heuristic-based first pass: searches each PDF text for the principal
engagement clause (``L'initiateur s'engage [irrévocablement] à acquérir
... au prix [unitaire] de X €``) and extracts the price the parser
*should* have stored. Compares with the stored offer_price and emits a
verdict per row:

- ``match`` : primary clause price == stored price → correct extraction
- ``mismatch`` : primary clause price differs from stored → likely FP
- ``no_engagement_clause`` : primary clause not found in 5 pages →
  manual review needed (surenchère filing, retrait obligatoire, ...)
- ``multiple_engagement_clauses`` : several primary clauses (e.g.
  surenchère mentioning both old + new price) → keeps the LAST one
  (final price) and flags for manual confirmation

Writes ``data/audits/p92_02b_ground_truth.csv`` with one row per sample
deal:
    deal_id, regulator_ref, target_name, year, selection,
    stored_price, primary_price, status, mismatch_category,
    principal_clause_excerpt
"""

from __future__ import annotations

import csv
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = REPO_ROOT / "data" / "audits" / "p92_02b_sample.csv"
OUT_CSV = REPO_ROOT / "data" / "audits" / "p92_02b_ground_truth.csv"

# Primary engagement clause: the canonical AMF formulation that drives the
# offer price. Allows for line breaks (PDF text extraction inserts them
# mid-clause) and variants. Real PDFs use both ASCII apostrophe and the curly
# U+2019; both are accepted via an explicit Unicode escape inside the regex.
_PRIMARY_CLAUSE = re.compile(
    "s['\u2019]\\s*engage\\s+(?:\\w+\\s+){0,3}[àa]\\s+acqu[ée]rir"
    "[\\s\\S]{0,400}?"
    "prix\\s+(?:unitaire\\s+)?(?:relev[ée]\\s+)?(?:modifi[ée]\\s+)?de\\s+"
    "(?P<amount>\\d{1,3}(?:[\\s.\\xa0]\\d{3})*(?:[,.\\d]\\d{1,4})?)"
    "\\s*(?:€|euros?)",
    re.IGNORECASE,
)

# Looser fallback: capture any "au prix [unitaire] de X €" clause in case the
# PDF wraps the verb across pages. Used only when _PRIMARY_CLAUSE finds zero.
_FALLBACK_PRICE = re.compile(
    "(?:au\\s+)?prix\\s+(?:unitaire\\s+)?(?:relev[ée]\\s+)?(?:modifi[ée]\\s+)?de\\s+"
    "(?P<amount>\\d{1,3}(?:[\\s.\\xa0]\\d{3})*(?:[,.\\d]\\d{1,4})?)"
    "\\s*(?:€|euros?)",
    re.IGNORECASE,
)


def _normalise_amount(raw: str) -> Decimal | None:
    s = re.sub(r"\s", "", raw).replace(",", ".")
    if s.count(".") > 1:
        head, _, tail = s.rpartition(".")
        s = head.replace(".", "") + "." + tail
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _read_pdf_text(pdf_path: Path, *, max_pages: int = 8) -> str:
    pieces: list[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pieces.append(page.get_text("text") or "")
    return "\n".join(pieces)


def _local_pdf(stored_path: str) -> Path | None:
    if not stored_path:
        return None
    rel = stored_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


def _excerpt_around(text: str, span: tuple[int, int], *, before: int = 80, after: int = 120) -> str:
    start = max(0, span[0] - before)
    end = min(len(text), span[1] + after)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _classify(  # noqa: PLR0911 — one branch per ground-truth verdict, keeps reading linear
    text: str, stored: Decimal | None
) -> tuple[str, str, Decimal | None, str]:
    """Return (status, mismatch_category, primary_price, excerpt)."""
    matches = list(_PRIMARY_CLAUSE.finditer(text))
    if not matches:
        # Fallback: any "au prix de X" clause — covers PDFs where the verb wraps
        # mid-sentence or where the engagement verb is implicit.
        fb = list(_FALLBACK_PRICE.finditer(text))
        if not fb:
            return ("no_engagement_clause", "", None, "")
        # Use the LAST fallback hit — surenchère / final filing typically restates
        # the new price near the end.
        m = fb[-1]
        primary = _normalise_amount(m.group("amount"))
        excerpt = _excerpt_around(text, m.span())
        if stored is None or primary is None:
            return ("fallback_only", "fallback", primary, excerpt)
        if primary == stored:
            return ("match_via_fallback", "", primary, excerpt)
        return ("mismatch_via_fallback", "fallback_disagrees", primary, excerpt)

    # Primary clause(s) found.
    last = matches[-1]
    primary = _normalise_amount(last.group("amount"))
    excerpt = _excerpt_around(text, last.span())
    status = "multiple_engagement_clauses" if len(matches) > 1 else "single_engagement_clause"

    if stored is None or primary is None:
        return (status, "primary_extraction_failed", primary, excerpt)
    if primary == stored:
        return (f"{status}_match", "", primary, excerpt)
    return (f"{status}_mismatch", "primary_differs", primary, excerpt)


def main() -> None:
    with SAMPLE_CSV.open(encoding="utf-8") as fh:
        sample = list(csv.DictReader(fh))

    rows: list[dict[str, object]] = []
    for s in sample:
        stored = _normalise_amount(s["offer_price"]) if s["offer_price"] else None
        pdf = _local_pdf(s["pdf_path"])
        if pdf is None:
            rows.append(
                {
                    **s,
                    "stored_price": str(stored) if stored is not None else "",
                    "primary_price": "",
                    "status": "missing_pdf",
                    "mismatch_category": "",
                    "principal_clause_excerpt": "",
                }
            )
            continue
        try:
            text = _read_pdf_text(pdf, max_pages=8)
        except Exception as exc:
            rows.append(
                {
                    **s,
                    "stored_price": str(stored) if stored is not None else "",
                    "primary_price": "",
                    "status": f"pdf_error:{type(exc).__name__}",
                    "mismatch_category": "",
                    "principal_clause_excerpt": str(exc)[:200],
                }
            )
            continue

        status, category, primary, excerpt = _classify(text, stored)
        rows.append(
            {
                **s,
                "stored_price": str(stored) if stored is not None else "",
                "primary_price": str(primary) if primary is not None else "",
                "status": status,
                "mismatch_category": category,
                "principal_clause_excerpt": excerpt,
            }
        )

    fieldnames = [
        "deal_id",
        "regulator_ref",
        "target_name",
        "year",
        "offer_price",
        "pdf_path",
        "selection",
        "stored_price",
        "primary_price",
        "status",
        "mismatch_category",
        "principal_clause_excerpt",
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary by status.
    counts: dict[str, int] = {}
    mismatches: list[dict[str, object]] = []
    for r in rows:
        st = str(r["status"])
        counts[st] = counts.get(st, 0) + 1
        if "mismatch" in st or st in {"no_engagement_clause", "missing_pdf"}:
            mismatches.append(r)

    print("=" * 72)
    print("P9.2 02b Step 0 — ground-truth auto-classification on 68-deal sample")
    print("=" * 72)
    print(f"total processed: {len(rows)}")
    print()
    print("by status:")
    for k in sorted(counts):
        print(f"  {k:<32}: {counts[k]}")
    print()
    print(f"flagged for manual review: {len(mismatches)}")
    print(f"CSV: {OUT_CSV}")


if __name__ == "__main__":
    main()
