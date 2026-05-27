"""P9.2 Step 0 — dry-run the current AMF parser on the 10 audited PDFs.

No DB write. Compares parser output vs manually-extracted truth from
docs/phase-09/p92_amf_extraction_manual.md.

Output: data/audits/p92_amf_parser_dryrun.csv (deal_ref, expected_price,
parser_output, status: match|miss|mismatch|n/a).
"""

from __future__ import annotations

import csv
import logging
from decimal import Decimal
from pathlib import Path

import structlog

# Quiet structlog so the WARN logs from the parser don't pollute stdout.
logging.basicConfig(level=logging.WARNING)
structlog.configure(
    processors=[
        structlog.processors.KeyValueRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
)

from src.ingestion.amf.parser import extract_pdf_metadata  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PDF_ROOT = REPO / "data" / "pdfs" / "fr"
OUT = REPO / "data" / "audits" / "p92_amf_parser_dryrun.csv"

# Truth from Step 0 manual extraction. (None = parser MUST NOT extract any
# price — this is the SERMA response-note case.)
SAMPLE: list[dict[str, str | Decimal | None]] = [
    {
        "ref": "216C1735",
        "rel": "2022/216C1735.pdf",
        "target": "CEGID GROUP",
        "expected_price": Decimal("61.00"),
        "doc_type": "conformity_decision",
    },
    {
        "ref": "219C0051",
        "rel": "2022/219C0051.pdf",
        "target": "TESSI",
        "expected_price": Decimal("160.00"),
        "doc_type": "deposit_notice",
    },
    {
        "ref": "223C0044",
        "rel": "2023/223C0044.pdf",
        "target": "SERMA GROUP",
        "expected_price": None,
        "doc_type": "response_note_no_price",
    },
    {
        "ref": "224C0830",
        "rel": "2024/224C0830.pdf",
        "target": "TIPIAK",
        "expected_price": Decimal("88.00"),
        "doc_type": "deposit_notice",
    },
    {
        "ref": "224C0915",
        "rel": "2024/224C0915.pdf",
        "target": "TRAVEL TECHNOLOGY INTERACTIVE",
        "expected_price": Decimal("2.85"),
        "doc_type": "deposit_notice",
    },
    {
        "ref": "225C0021",
        "rel": "2026/225C0021.pdf",
        "target": "NEOEN",
        "expected_price": Decimal("39.85"),
        "doc_type": "deposit_notice",
    },
    {
        "ref": "225C0741",
        "rel": "2025/225C0741.pdf",
        "target": "FINANCIERE MONCEY",
        "expected_price": Decimal("133.00"),
        "doc_type": "conformity_decision_mixed",
    },
    {
        "ref": "225C0921",
        "rel": "2025/225C0921.pdf",
        "target": "M2I",
        "expected_price": Decimal("8.50"),
        "doc_type": "conformity_decision",
    },
    {
        "ref": "225C2081",
        "rel": "2025/225C2081.pdf",
        "target": "SOCIETE DE TAYNINH",
        "expected_price": Decimal("0.11"),
        "doc_type": "deposit_notice",
    },
    {
        "ref": "225C2156",
        "rel": "2026/225C2156.pdf",
        "target": "PRODWARE",
        "expected_price": Decimal("28.00"),
        "doc_type": "conformity_decision",
    },
]


def classify(expected: Decimal | None, parsed: Decimal | None) -> str:
    if expected is None and parsed is None:
        return "match_none"
    if expected is None and parsed is not None:
        return "false_positive"
    if expected is not None and parsed is None:
        return "miss"
    # Both non-None
    assert expected is not None and parsed is not None
    if parsed == expected:
        return "match"
    return "mismatch"


def main() -> None:
    rows: list[dict[str, str]] = []
    print(f"{'REF':<10} {'TARGET':<35} {'EXPECTED':>10} {'PARSED':>10}  STATUS")
    print("-" * 90)
    for s in SAMPLE:
        pdf = PDF_ROOT / str(s["rel"])
        if not pdf.exists():
            rows.append(
                {
                    "ref": str(s["ref"]),
                    "target": str(s["target"]),
                    "doc_type": str(s["doc_type"]),
                    "expected": str(s["expected_price"]),
                    "parsed": "PDF_NOT_FOUND",
                    "status": "missing_pdf",
                }
            )
            print(f"{s['ref']:<10} {str(s['target'])[:35]:<35} {'-':>10} {'-':>10}  PDF_NOT_FOUND")
            continue
        try:
            md = extract_pdf_metadata(pdf, max_pages=5)
        except Exception as exc:
            rows.append(
                {
                    "ref": str(s["ref"]),
                    "target": str(s["target"]),
                    "doc_type": str(s["doc_type"]),
                    "expected": str(s["expected_price"]),
                    "parsed": f"EXC: {exc}",
                    "status": "exception",
                }
            )
            print(f"{s['ref']:<10} {str(s['target'])[:35]:<35} {'-':>10} EXC")
            continue
        parsed = md.offer_price
        status = classify(s["expected_price"], parsed)  # type: ignore[arg-type]
        exp_str = str(s["expected_price"]) if s["expected_price"] is not None else "(none)"
        parsed_str = str(parsed) if parsed is not None else "(none)"
        print(
            f"{s['ref']:<10} {str(s['target'])[:35]:<35} "
            f"{exp_str:>10} {parsed_str:>10}  {status}"
        )
        rows.append(
            {
                "ref": str(s["ref"]),
                "target": str(s["target"]),
                "doc_type": str(s["doc_type"]),
                "expected": exp_str,
                "parsed": parsed_str,
                "status": status,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["ref", "target", "doc_type", "expected", "parsed", "status"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved -> {OUT.relative_to(REPO)}")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\nSummary:")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
