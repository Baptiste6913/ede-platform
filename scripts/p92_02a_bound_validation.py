"""P9.2 02a commit #2 — empirical validation of the AMF bound [0.01, 100000].

Replays `_extract_first_price` on the 80-deal audit sample with the post-fix
parser and classifies each extraction against the proposed AMF bound:

- `verified_cash`          : 0.01 <= price <= 100000  (in-bounds)
- `failed_validation`      : price < 0.01 OR price > 100000
- `suspect_low_unverified` : price is None (parser silent)

Targets to confirm:

- LV GROUP 222C0375 (price 10000) MUST land `verified_cash` — it is a real
  small-cap retrait price (Finexsi-validated, see commit #1 SELECTIRENTE
  verification notes). The upper bound was widened from the per-default 1000
  to 100000 specifically for this case.
- NEOEN OCEANE controvalore 101 382 (if present in the sample, ref 225C0021
  / 225C0297) MUST land `failed_validation` — that figure is the OCEANE
  redemption value, not an offer price, so the bound is doing its job.

Writes `data/audits/p92_02a_bound_validation.csv` with one row per deal.
"""

from __future__ import annotations

import csv
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF

from src.ingestion.amf.parser import _extract_first_price

REPO = Path(__file__).resolve().parents[1]
SAMPLE_CSV = REPO / "data" / "audits" / "p92_02a_sample.csv"
OUT_CSV = REPO / "data" / "audits" / "p92_02a_bound_validation.csv"

PRICE_LOWER_AMF = Decimal("0.01")
PRICE_UPPER_AMF = Decimal("100000")


def _read_pdf_text(pdf_path: Path, *, max_pages: int = 5) -> str:
    pieces: list[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pieces.append(page.get_text("text") or "")
    return "\n".join(pieces)


def _local_pdf(stored_path: str) -> Path | None:
    rel = stored_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO / rel
    return candidate if candidate.is_file() else None


def _derive_flag(price: Decimal | None) -> str:
    if price is None:
        return "suspect_low_unverified"
    if price < PRICE_LOWER_AMF or price > PRICE_UPPER_AMF:
        return "failed_validation"
    return "verified_cash"


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
                    "extracted_price": "",
                    "derived_flag": "missing_pdf",
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
                    "extracted_price": "",
                    "derived_flag": f"pdf_error:{type(exc).__name__}",
                }
            )
            continue

        price, _ = _extract_first_price(text)
        flag = _derive_flag(price)
        rows.append(
            {
                "deal_id": s["deal_id"],
                "regulator_ref": s["regulator_ref"],
                "target_name": s["target_name"],
                "year": s["year"],
                "extracted_price": str(price) if price is not None else "",
                "derived_flag": flag,
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
                "extracted_price",
                "derived_flag",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["derived_flag"])] = counts.get(str(r["derived_flag"]), 0) + 1
    print("=" * 70)
    print(f"P9.2 02a bound validation -- AMF [{PRICE_LOWER_AMF}, {PRICE_UPPER_AMF}]")
    print("=" * 70)
    for k, v in sorted(counts.items()):
        print(f"  {k:<28}: {v}")
    print()

    # Spotlight the failed_validation rows: these are the deals where the bound
    # rejects an extraction. Goal: only OCEANE-class artefacts here, no real
    # offer prices.
    failed = [r for r in rows if r["derived_flag"] == "failed_validation"]
    if failed:
        print(f"failed_validation rows ({len(failed)}):")
        for r in failed:
            print(
                f"  {r['regulator_ref']:<10} {r['target_name'][:35]:<35} "
                f"price={r['extracted_price']}"
            )
        print()

    # Targeted spotlight: LV GROUP must be IN-bounds.
    lv_rows = [r for r in rows if r["regulator_ref"] == "222C0375"]
    if lv_rows:
        r = lv_rows[0]
        print(f"LV GROUP 222C0375: price={r['extracted_price']!r} flag={r['derived_flag']!r}")

    print()
    print(f"CSV: {OUT_CSV}")


if __name__ == "__main__":
    main()
