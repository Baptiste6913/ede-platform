"""Phase 6 Step 0 helper — enrich the raw labelling CSV with two
heuristic columns to speed up Baptiste's manual review.

Adds:
    days_since_close_estimated
        = days_open - typical_offer_duration_by_jurisdiction
        Heuristics from market practice:
          FR : 60 j  (25 j de bourse procédure normale + 10 j réouverture + clearances)
          IT : 75 j  (15-40 j adhésion + 5 j riapertura + clearances)
          DE : 90 j  (4-10 sem Annahmefrist + 2 sem weitere + Vollzug)

    preliminary_label_guess
        > 90  →  "likely 1 if no failure news"
        0-90  →  "verify"
        < 0   →  "likely pending NULL"

Run:
    python scripts/enrich_labelling_csv.py
        [input=artifacts/phase-06/deals_to_label.csv]
        [output=artifacts/phase-06/deals_to_label_v2.csv]
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_TYPICAL_DURATION_DAYS: dict[str, int] = {
    "FR": 60,
    "IT": 75,
    "DE": 90,
}


def _guess(delta: int) -> str:
    if delta > 90:  # noqa: PLR2004
        return "likely 1 if no failure news"
    if delta >= 0:
        return "verify"
    return "likely pending NULL"


def enrich(input_path: Path, output_path: Path) -> tuple[int, dict[str, int]]:
    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    # Insert the two new columns right after `days_open` so the operator
    # sees them next to the source value.
    new_cols = ["days_since_close_estimated", "preliminary_label_guess"]
    if "days_open" in fieldnames:
        idx = fieldnames.index("days_open") + 1
        out_fields = fieldnames[:idx] + new_cols + fieldnames[idx:]
    else:
        out_fields = [*fieldnames, *new_cols]

    summary: dict[str, int] = {
        "likely 1 if no failure news": 0,
        "verify": 0,
        "likely pending NULL": 0,
        "unknown_jurisdiction": 0,
        "missing_days_open": 0,
    }

    for row in rows:
        jur = row.get("juridiction", "").strip()
        days_open_raw = row.get("days_open", "").strip()
        typical = _TYPICAL_DURATION_DAYS.get(jur)
        if typical is None:
            row["days_since_close_estimated"] = ""
            row["preliminary_label_guess"] = "unknown_jurisdiction"
            summary["unknown_jurisdiction"] += 1
            continue
        if not days_open_raw:
            row["days_since_close_estimated"] = ""
            row["preliminary_label_guess"] = "missing_days_open"
            summary["missing_days_open"] += 1
            continue
        try:
            days_open = int(days_open_raw)
        except ValueError:
            row["days_since_close_estimated"] = ""
            row["preliminary_label_guess"] = "missing_days_open"
            summary["missing_days_open"] += 1
            continue
        delta = days_open - typical
        row["days_since_close_estimated"] = str(delta)
        guess = _guess(delta)
        row["preliminary_label_guess"] = guess
        summary[guess] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows), summary


def main(argv: list[str]) -> int:
    default_in = Path("artifacts/phase-06/deals_to_label.csv")
    default_out = Path("artifacts/phase-06/deals_to_label_v2.csv")
    in_path = Path(argv[1]) if len(argv) > 1 else default_in
    out_path = Path(argv[2]) if len(argv) > 2 else default_out  # noqa: PLR2004 — argv index

    if not in_path.exists():
        print(f"error: input not found at {in_path}", file=sys.stderr)
        return 2

    count, summary = enrich(in_path, out_path)
    print(f"Enriched {count} rows -> {out_path}")
    for key in ("likely 1 if no failure news", "verify", "likely pending NULL"):
        print(f"  {key:35s} {summary.get(key, 0):>4d}")
    for key in ("unknown_jurisdiction", "missing_days_open"):
        if summary.get(key):
            print(f"  {key:35s} {summary[key]:>4d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
