"""P9.2 02a post-commit #1 — re-run the regex impact comparator with the
NOW-MERGED `_extract_first_price` (regex widening + NBSP fix + valeur-nominale
exclusion).

Compares the legacy regex (`_REGEX_OLD`, same broken `\\xa0` + mandatory
decimals as the original parser) against the live post-fix
`src.ingestion.amf.parser._extract_first_price`. Used to confirm:

- the 17 recovered + 4 corrections gains from the pre-commit dry-run are
  preserved (no regressions),
- SELECTIRENTE 218C2043 moves from `changed_extracted 63` to either
  `unchanged_silent` (no other match) or `recovered` (a real downstream price)
  — i.e. the nominal-value exclusion does its job.

Writes `data/audits/p92_02a_regex_impact_post_fix.csv` with one row per deal.
"""

from __future__ import annotations

import csv
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF

from src.ingestion.amf.parser import _extract_first_price  # post-fix logic

REPO = Path(__file__).resolve().parents[1]
SAMPLE_CSV = REPO / "data" / "audits" / "p92_02a_sample.csv"
OUT_CSV = REPO / "data" / "audits" / "p92_02a_regex_impact_post_fix.csv"

# Legacy production regex (the one in prod BEFORE commit #1). Frozen here so
# the comparator is self-contained and the result does not silently change if
# the parser regex is tweaked again.
_REGEX_OLD = re.compile(
    r"(?P<amount>\d{1,3}(?:[ \\xa0\.]\d{3})*[,\.]\d{2,4})\s*" r"(?P<currency>€|EUR|CHF|GBP|USD)",
    re.IGNORECASE,
)


def _normalise_amount(raw: str) -> Decimal | None:
    s = raw.replace("\xa0", "").replace(" ", "")
    s = s.replace(",", ".")
    if s.count(".") > 1:
        head, _, tail = s.rpartition(".")
        s = head.replace(".", "") + "." + tail
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _old_match(text: str) -> Decimal | None:
    m = _REGEX_OLD.search(text)
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
        except Exception as exc:
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

        old_amt = _old_match(text)
        new_amt, _ = _extract_first_price(text)
        transition = _classify_transition(old_amt, new_amt)

        rows.append(
            {
                "deal_id": s["deal_id"],
                "regulator_ref": s["regulator_ref"],
                "target_name": s["target_name"],
                "year": s["year"],
                "old_amount": str(old_amt) if old_amt is not None else "",
                "new_amount": str(new_amt) if new_amt is not None else "",
                "transition": transition,
                "amount_context": "",
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

    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["transition"])] = counts.get(str(r["transition"]), 0) + 1
    print("=" * 70)
    print("P9.2 02a regex impact POST-FIX -- legacy regex vs _extract_first_price")
    print("=" * 70)
    for k, v in sorted(counts.items()):
        print(f"  {k:<24}: {v}")
    print()
    print(f"CSV: {OUT_CSV}")

    # Targeted SELECTIRENTE check
    selectirente_rows = [r for r in rows if r["regulator_ref"] == "218C2043"]
    if selectirente_rows:
        r = selectirente_rows[0]
        print()
        print(
            f"SELECTIRENTE 218C2043: old={r['old_amount']!r} new={r['new_amount']!r} "
            f"transition={r['transition']!r}"
        )


if __name__ == "__main__":
    main()
