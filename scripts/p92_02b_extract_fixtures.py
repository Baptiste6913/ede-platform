"""P9.2 02b Step 1a — build 17 test-fixture excerpts from the corpus PDFs.

For every case in ``CASES`` (14 false positives + 3 false alarms), we:

1. Find the local PDF under ``data/pdfs/fr/<year>/<ref>.pdf``.
2. Extract the full text via PyMuPDF.
3. Locate the principal engagement-clause amount (the *correct* offer price)
   and capture a ~1000-char window around it.
4. Verify the bug reproduces on the excerpt itself:
   - For FP cases: the legacy `_extract_first_price` on the excerpt must
     return the (wrong) stored value, so the failing red test is
     reproducible on the excerpt alone (not just the full PDF).
   - For false-alarm cases: the legacy parser must already return the
     correct value on the excerpt.
5. Write the excerpt to ``tests/fixtures/p92_02b/<ref>_excerpt.txt``.

If a case does not reproduce, we widen the window until it does (up to
2500 chars). This guarantees the test file pins the bug, not the fix.
"""

from __future__ import annotations

import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF

from src.ingestion.amf.parser import _extract_first_price

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "p92_02b"

# (ref, year, target, true_price, stored_price, pattern, kind)
CASES: list[tuple[str, int, str, str, str, str, str]] = [
    # ---- 14 FP cases (RED tests — current parser returns stored, fix must return true)
    ("224C0915", 2024, "TRAVEL TECHNOLOGY INTERACTIVE", "2.85", "2.34", "BLOCK_PURCHASE", "fp"),
    ("224C1289", 2024, "TRAVEL TECHNOLOGY INTERACTIVE", "2.85", "2.34", "BLOCK_PURCHASE", "fp"),
    ("218C1907", 2018, "SERMA GROUP", "235", "229.19", "BLOCK_PURCHASE", "fp"),
    ("218C2028", 2018, "SERMA GROUP", "235", "229.19", "BLOCK_PURCHASE", "fp"),
    ("221C1910", 2021, "GENKYOTEX", "2.85", "2.80", "DIVIDEND_TRAP", "fp"),
    ("218C1043", 2018, "CFI", "1.00", "0.83", "SURENCHERE", "fp"),
    ("220C4135", 2020, "LE BELIER", "38.18", "35.12", "DIVIDEND_TRAP", "fp"),
    ("224C1700", 2024, "GALIMMO", "14.83", "9.02", "BLOCK_PURCHASE", "fp"),
    ("224C2193", 2024, "NHOA", "1.25", "1.10", "SURENCHERE", "fp"),
    ("224C1145", 2024, "OSMOZIS", "15", "13.50", "DIVIDEND_TRAP", "fp"),
    ("223C2035", 2023, "TECHNICOLOR CREATIVE STUDIOS", "1.63", "0.01", "OCEANE_BSA", "fp"),
    ("226C0661", 2026, "MEDIA 6", "9.89", "9.69", "SURENCHERE", "fp"),
    ("226C0645", 2026, "MEDIA 6", "9.89", "9.69", "SURENCHERE", "fp"),
    ("225C1227", 2025, "GROUPE ETPO", "82.33", "61", "DIVIDEND_TRAP", "fp"),
    # ---- 3 false alarms (GREEN tests — current parser is correct, fix must preserve)
    ("226C0550", 2026, "TERACT", "3.12", "3.12", "MULTI_BULLET", "false_alarm"),
    ("226C0157", 2026, "TERACT", "3.12", "3.12", "MULTI_BULLET", "false_alarm"),
    ("224C1861", 2024, "NHOA", "1.25", "1.25", "DORENAVANT_PHRASING", "false_alarm"),
]


def _read_pdf_text(pdf_path: Path) -> str:
    pieces: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pieces.append(page.get_text("text") or "")
    return "\n".join(pieces)


def _find_true_price_pos(text: str, true_price: str) -> int | None:
    """Locate the engagement-clause occurrence of the true price.

    Searches for the literal price string in the text (handling the comma vs
    dot decimal separator). Returns the position of the first hit that is
    immediately followed by `€` or `euros`, since other unrelated numbers may
    coincide. Falls back to the first hit if no euro-tagged hit is found.
    """
    candidates_str: list[str] = []
    if "." in true_price:
        head, tail = true_price.split(".")
        candidates_str.append(f"{head},{tail}")
        candidates_str.append(f"{head}.{tail}")
    else:
        candidates_str.append(true_price)

    for cand in candidates_str:
        idx = 0
        while idx < len(text):
            pos = text.find(cand, idx)
            if pos < 0:
                break
            # Check what follows: € or 'euros' within next 6 chars (allow whitespace)
            tail_window = text[pos + len(cand) : pos + len(cand) + 6]
            if re.match(r"\s*(?:€|euros?)", tail_window, re.IGNORECASE):
                return pos
            idx = pos + 1
    # Fallback: first naïve occurrence
    for cand in candidates_str:
        pos = text.find(cand)
        if pos >= 0:
            return pos
    return None


def _excerpt(text: str, center: int, half_window: int) -> str:
    start = max(0, center - half_window)
    end = min(len(text), center + half_window)
    return text[start:end]


def _legacy_extracts(excerpt: str) -> Decimal | None:
    price, _ = _extract_first_price(excerpt)
    return price


def _build_excerpt_for_case(
    ref: str, year: int, true_price: str, stored_price: str, kind: str
) -> tuple[str, int]:
    """Find the smallest excerpt that reproduces the parser behaviour.

    For FP cases: the legacy parser on the excerpt must return ``stored_price``
    (the wrong one) so the failing test pins the bug on the excerpt itself.
    For false-alarm cases: the legacy parser must return ``true_price``
    (the correct one) so the green test confirms preservation.
    """
    del year  # the on-disk folder is the announcement_date year, not the ref prefix
    candidates = list((REPO_ROOT / "data" / "pdfs" / "fr").rglob(f"{ref}.pdf"))
    if not candidates:
        raise FileNotFoundError(f"PDF for ref {ref} not found under data/pdfs/fr/")
    pdf_path = candidates[0]
    text = _read_pdf_text(pdf_path)
    center = _find_true_price_pos(text, true_price)
    if center is None:
        # No clean true-price anchor — fall back to a 2500-char excerpt at the
        # PDF head. Most engagement clauses live in the first 1500 chars.
        excerpt = text[:2500]
        return excerpt, len(excerpt)

    stored_decimal = Decimal(stored_price.replace(",", "."))
    true_decimal = Decimal(true_price.replace(",", "."))
    target_legacy = stored_decimal if kind == "fp" else true_decimal

    # For FP cases the excerpt must EXTRACT the stored wrong value with the
    # legacy parser AND CONTAIN the engagement-clause "s'engage" verb anywhere
    # before the true_price location — otherwise no fix can ever flip the test
    # to green on the excerpt alone. False-alarm cases need only the legacy to
    # return the true value.
    needs_engage_verb = kind == "fp"
    for half_window in (400, 600, 900, 1300, 2000, 3000, 5000):
        excerpt = _excerpt(text, center, half_window)
        got = _legacy_extracts(excerpt)
        if got != target_legacy:
            continue
        if not needs_engage_verb:
            return excerpt, half_window * 2
        # Need an engagement verb somewhere in the excerpt for the Step 1b fix
        # to have anything to anchor on. Accept either "s'engage" (any
        # conjugation) or the bare "s'engag" stem.
        has_engage = re.search(r"s['\u2019]\s*engag", excerpt, re.IGNORECASE) is not None
        if has_engage:
            return excerpt, half_window * 2
    # Last resort: ship the largest excerpt and let the test reveal the gap.
    excerpt = _excerpt(text, center, 5000)
    return excerpt, len(excerpt)


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    summary: list[str] = []
    for ref, year, target, true_p, stored_p, pattern, kind in CASES:
        try:
            excerpt, span = _build_excerpt_for_case(ref, year, true_p, stored_p, kind)
        except FileNotFoundError as exc:
            summary.append(f"  ✗ {ref} {target}: PDF missing ({exc})")
            continue
        legacy = _legacy_extracts(excerpt)
        out_path = FIXTURES_DIR / f"{ref}_excerpt.txt"
        out_path.write_text(excerpt, encoding="utf-8")

        if kind == "fp":
            expected_legacy = Decimal(stored_p.replace(",", "."))
        else:
            expected_legacy = Decimal(true_p.replace(",", "."))

        flag = "OK" if legacy == expected_legacy else "MISMATCH"
        summary.append(
            f"  {flag:<8} {ref} {target[:30]:<30} {kind:<11} "
            f"legacy={legacy!s:<10} expected={expected_legacy!s:<10} ({span} chars, {pattern})"
        )

    print("=" * 90)
    print("P9.2 02b Step 1a — excerpt extraction summary")
    print("=" * 90)
    for line in summary:
        print(line)
    print()
    print(f"Fixtures written under: {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
