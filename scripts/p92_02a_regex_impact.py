"""P9.2 02a pré-commit #1 — measure the impact of the proposed regex fix.

Applies BOTH the current and the proposed `_PRICE_REGEX` on the 80
deals already sampled in `data/audits/p92_02a_sample.csv`. For each
deal we capture the FIRST-MATCH amount under each regex and classify
the transition. The output CSV `p92_02a_regex_impact_before_after.csv`
contains one row per deal with both amounts + a transition label.

Transitions:
- `unchanged_silent`           — both old and new return None
- `unchanged_extracted`        — both extract the same amount
- `changed_extracted`          — both extract, but amounts differ
                                 (should NOT happen for a pure
                                 acceptance-class widening)
- `recovered`                  — old=None, new=extracted (the
                                 intended +volume win; needs manual
                                 verification to label correct / false)
- `lost`                       — old=extracted, new=None (should be
                                 zero — the new regex is strictly more
                                 permissive)

Manual verification of `recovered` rows happens in a second pass
(this script just produces the transitions). The user reviews the
gain/cost ratio before any commit lands.
"""

from __future__ import annotations

import csv
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF

REPO = Path(__file__).resolve().parents[1]
SAMPLE_CSV = REPO / "data" / "audits" / "p92_02a_sample.csv"
OUT_CSV = REPO / "data" / "audits" / "p92_02a_regex_impact_before_after.csv"

# Current production regex from src/ingestion/amf/parser.py:65-68.
# NB: the `\\xa0` literal inside the raw-string character class matches the
# 4 literal characters `\`, `x`, `a`, `0` — that is the documented bug. The
# `[,\.]\d{2,4}` decimal portion is mandatory — the second documented bug.
_REGEX_OLD = re.compile(
    r"(?P<amount>\d{1,3}(?:[ \\xa0\.]\d{3})*[,\.]\d{2,4})\s*"
    r"(?P<currency>€|EUR|CHF|GBP|USD)",
    re.IGNORECASE,
)

# Proposed regex (commit #1 of 02a). Two fixes in one diff:
# - `[ \\xa0\.]` -> `[\s .]`  : Unicode whitespace class catches the real
#   NBSP byte that the broken `\xa0` literal was supposed to match. `.` and
#   space stay valid thousand separators.
# - `[,\.]\d{2,4}` -> `(?:[,\.]\d{1,4})?` : decimal portion becomes optional,
#   matches integer prices ("88 EUR") and decimal prices with 1-4 fractional
#   digits.
_REGEX_NEW = re.compile(
    r"(?P<amount>\d{1,3}(?:[\s .]\d{3})*(?:[,\.]\d{1,4})?)\s*"
    r"(?P<currency>€|EUR|CHF|GBP|USD)",
    re.IGNORECASE,
)


def _normalise_amount(raw: str) -> Decimal | None:
    """Mirror of `src/ingestion/amf/parser.py:_extract_first_price`
    normalisation — strip thousand separators (`.` and whitespace), then
    swap `,` -> `.` for Decimal parsing. The same logic applies to both
    regex outputs so the comparison stays apples-to-apples."""
    s = raw.replace("\xa0", "").replace(" ", "")
    s = s.replace(",", ".")
    if s.count(".") > 1:
        head, _, tail = s.rpartition(".")
        s = head.replace(".", "") + "." + tail
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _first_match(regex: re.Pattern[str], text: str) -> Decimal | None:
    m = regex.search(text)
    if not m:
        return None
    return _normalise_amount(m.group("amount"))


def _read_pdf_text(pdf_path: Path, *, max_pages: int = 5) -> str:
    pieces: list[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pieces.append(page.get_text("text") or "")
    return "\n".join(pieces)


def _classify_transition(old: Decimal | None, new: Decimal | None) -> str:
    if old is None and new is None:
        return "unchanged_silent"
    if old is None and new is not None:
        return "recovered"
    if old is not None and new is None:
        return "lost"
    if old == new:
        return "unchanged_extracted"
    return "changed_extracted"


def _local_pdf(stored_path: str) -> Path | None:
    rel = stored_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO / rel
    return candidate if candidate.is_file() else None


def main() -> None:
    with SAMPLE_CSV.open(encoding="utf-8") as fh:
        sample = list(csv.DictReader(fh))

    rows: list[dict[str, object]] = []
    for s in sample:
        pdf = _local_pdf(s["pdf_path"])
        if pdf is None:
            rows.append(
                {
                    "deal_id": s["deal_id"],
                    "regulator_ref": s["regulator_ref"],
                    "target_name": s["target_name"],
                    "year": s["year"],
                    "old_amount": "",
                    "new_amount": "",
                    "transition": "missing_pdf",
                    "amount_context": "",
                }
            )
            continue
        try:
            text = _read_pdf_text(pdf, max_pages=5)
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "deal_id": s["deal_id"],
                    "regulator_ref": s["regulator_ref"],
                    "target_name": s["target_name"],
                    "year": s["year"],
                    "old_amount": "",
                    "new_amount": "",
                    "transition": f"pdf_error:{type(exc).__name__}",
                    "amount_context": "",
                }
            )
            continue

        old_amt = _first_match(_REGEX_OLD, text)
        new_amt = _first_match(_REGEX_NEW, text)
        transition = _classify_transition(old_amt, new_amt)

        # For `recovered` rows, capture the ±50-char window around the new
        # match so the manual verification pass can label correct vs false
        # without re-reading the full PDF.
        context = ""
        if transition == "recovered":
            m = _REGEX_NEW.search(text)
            if m:
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 40)
                context = text[start:end].replace("\n", " ").strip()
        elif transition == "changed_extracted":
            m_new = _REGEX_NEW.search(text)
            if m_new:
                start = max(0, m_new.start() - 80)
                end = min(len(text), m_new.end() + 40)
                context = text[start:end].replace("\n", " ").strip()

        rows.append(
            {
                "deal_id": s["deal_id"],
                "regulator_ref": s["regulator_ref"],
                "target_name": s["target_name"],
                "year": s["year"],
                "old_amount": str(old_amt) if old_amt is not None else "",
                "new_amount": str(new_amt) if new_amt is not None else "",
                "transition": transition,
                "amount_context": context,
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "deal_id",
                "regulator_ref",
                "target_name",
                "year",
                "old_amount",
                "new_amount",
                "transition",
                "amount_context",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["transition"])] = counts.get(str(r["transition"]), 0) + 1
    print("=" * 60)
    print("P9.2 02a regex impact -- before/after on 80 deals")
    print("=" * 60)
    for k, v in sorted(counts.items()):
        print(f"  {k:<24}: {v}")
    print()
    print(f"CSV: {OUT_CSV}")


if __name__ == "__main__":
    main()
