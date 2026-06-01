"""P9.2 02b Step 1h — re-run the post-fix AMF parser on every FR
verified_cash deal and compare with the price currently stored in the DB.

Categorisation per deal:

- ``UNCHANGED``        — same `offer_price`, no DB update needed.
- ``CORRECTED``        — different `offer_price`, new value from a
                          high-confidence source (`engagement_clause`,
                          `surenchere_raised`). Candidates for the
                          Step 1i DB update.
- ``NEW_DIFFERENT``    — different `offer_price`, new value from
                          `fallback_first_match` (low confidence). The
                          new logic happens to pick a different value
                          than the legacy did on the same code path —
                          surfaces a fragile case the user should review
                          before any DB write.
- ``PARSER_FAIL``      — new value is `None` where the old was not.
                          Means the new logic regressed somewhere.
                          Always needs investigation.
- ``NEW_EXTRACT``      — new value is not `None` where the old was
                          `None`. Should not happen on the verified_cash
                          subset (those rows have a price by definition).
                          If it appears, indicates DB / pipeline drift.

Writes two artefacts:

- ``data/audits/p92_02b_re_run_comparison.csv``  — gitignored, one row
  per re-parsed deal with full context (old/new prices, new source
  label, delta, pdf_path, manual_review flag).
- ``docs/phase-09/p92_02b_re_run_audit.md``  — tracked synthesis with
  counts + sample tables + full lists for NEW_DIFFERENT and
  PARSER_FAIL.

This script does NOT modify the DB. Step 1i applies the
high-confidence corrections after the user signs off on the report.
"""

from __future__ import annotations

import asyncio
import csv
import statistics
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal
from src.core.settings import get_settings
from src.ingestion.amf.parser import OfferPriceSource, extract_pdf_metadata

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "data" / "audits" / "p92_02b_re_run_comparison.csv"
OUT_MD = REPO_ROOT / "docs" / "phase-09" / "p92_02b_re_run_audit.md"

# Sources whose corrections the script trusts enough to mark a
# `CORRECTED` row instead of `NEW_DIFFERENT`.
_HIGH_CONFIDENCE_SOURCES = {
    OfferPriceSource.ENGAGEMENT_CLAUSE,
    OfferPriceSource.SURENCHERE_RAISED,
    OfferPriceSource.ENGAGEMENT_CLAUSE_MULTI_BULLET,
    OfferPriceSource.DIVIDEND_CUM_ANCHORED,
}


def _local_pdf(stored_path: str | None) -> Path | None:
    if not stored_path:
        return None
    rel = stored_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


def _categorise(
    old: Decimal | None,
    new: Decimal | None,
    source: OfferPriceSource,
) -> str:
    if old is None and new is None:
        return "UNCHANGED"
    if old is None and new is not None:
        return "NEW_EXTRACT"
    if old is not None and new is None:
        return "PARSER_FAIL"
    assert old is not None and new is not None  # mypy
    if old == new:
        return "UNCHANGED"
    if source in _HIGH_CONFIDENCE_SOURCES:
        return "CORRECTED"
    return "NEW_DIFFERENT"


async def _load_verified_cash() -> (
    list[tuple[int, str, str, int | None, Decimal | None, str | None]]
):
    """Return [(deal_id, regulator_ref, target_name, year, offer_price, pdf_path), ...]
    for every FR verified_cash row."""
    engine = create_async_engine(get_settings().database_url, echo=False, future=True)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    out: list[tuple[int, str, str, int | None, Decimal | None, str | None]] = []
    async with sm() as session:
        stmt = (
            select(Deal)
            .where(
                Deal.juridiction == "FR",
                Deal.offer_price_quality_flag == "verified_cash",
            )
            .order_by(Deal.id)
        )
        deals = (await session.execute(stmt)).scalars().all()
        for d in deals:
            year = d.announcement_date.year if d.announcement_date else None
            out.append((d.id, d.regulator_ref, d.target_name, year, d.offer_price, d.pdf_path))
    await engine.dispose()
    return out


def _make_row(
    deal_id: int,
    ref: str,
    target: str,
    year: int | None,
    old: Decimal | None,
    new: Decimal | None,
    source: OfferPriceSource,
    category: str,
    pdf_path: str | None,
) -> dict[str, object]:
    delta_eur: str = ""
    delta_pct: str = ""
    if old is not None and new is not None and old not in (new, 0):
        delta_eur = str(new - old)
        try:
            delta_pct = f"{(new - old) / old * 100:.2f}"
        except (ZeroDivisionError, ArithmeticError):
            delta_pct = ""
    return {
        "deal_id": deal_id,
        "regulator_ref": ref,
        "target_name": target,
        "year": year if year is not None else "",
        "old_offer_price": str(old) if old is not None else "",
        "new_offer_price": str(new) if new is not None else "",
        "new_source": source.value,
        "delta_eur": delta_eur,
        "delta_pct": delta_pct,
        "category": category,
        "pdf_path": pdf_path or "",
        "manual_review_needed": "Y" if category in {"NEW_DIFFERENT", "PARSER_FAIL"} else "N",
    }


async def _re_run() -> None:
    print("[STEP-1h] loading FR verified_cash from DB ...")
    deals = await _load_verified_cash()
    total = len(deals)
    print(f"[STEP-1h] {total} deals to re-parse")

    rows: list[dict[str, object]] = []
    skipped_no_pdf = 0
    for idx, (deal_id, ref, target, year, old_price, pdf_path) in enumerate(deals, start=1):
        local = _local_pdf(pdf_path)
        if local is None:
            skipped_no_pdf += 1
            rows.append(
                _make_row(
                    deal_id,
                    ref,
                    target,
                    year,
                    old_price,
                    None,
                    OfferPriceSource.NO_MATCH,
                    "PARSER_FAIL",
                    pdf_path,
                )
            )
            continue
        try:
            md = extract_pdf_metadata(local)
        except Exception as exc:
            print(f"  ERR  {ref} {target[:30]}: {type(exc).__name__}: {exc}")
            rows.append(
                _make_row(
                    deal_id,
                    ref,
                    target,
                    year,
                    old_price,
                    None,
                    OfferPriceSource.NO_MATCH,
                    "PARSER_FAIL",
                    pdf_path,
                )
            )
            continue

        new_price = md.offer_price
        source = md.extraction_source
        category = _categorise(old_price, new_price, source)
        rows.append(
            _make_row(deal_id, ref, target, year, old_price, new_price, source, category, pdf_path)
        )
        if idx % 100 == 0:
            print(f"[STEP-1h] progress: {idx}/{total} (last category={category})")

    _write_csv(rows)
    _write_md(rows, skipped_no_pdf=skipped_no_pdf)
    _print_summary(rows, skipped_no_pdf=skipped_no_pdf)


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "deal_id",
        "regulator_ref",
        "target_name",
        "year",
        "old_offer_price",
        "new_offer_price",
        "new_source",
        "delta_eur",
        "delta_pct",
        "category",
        "pdf_path",
        "manual_review_needed",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _bucket(rows: list[dict[str, object]], key: str) -> Counter[str]:
    return Counter(str(r[key]) for r in rows)


def _top_corrected(rows: list[dict[str, object]], n: int = 20) -> list[dict[str, object]]:
    corrected = [r for r in rows if r["category"] == "CORRECTED"]

    # Sort by |delta_pct| descending so the most material corrections come first.
    def _abs_pct(r: dict[str, object]) -> float:
        try:
            return abs(float(str(r["delta_pct"]))) if r["delta_pct"] else 0.0
        except ValueError:
            return 0.0

    return sorted(corrected, key=_abs_pct, reverse=True)[:n]


def _write_md(  # noqa: PLR0912, PLR0915 — linear narrative section by section
    rows: list[dict[str, object]], *, skipped_no_pdf: int
) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    cat_counts = _bucket(rows, "category")
    src_counts_corrected = Counter(
        str(r["new_source"]) for r in rows if r["category"] == "CORRECTED"
    )

    total = len(rows)
    corrected = [r for r in rows if r["category"] == "CORRECTED"]
    new_different = [r for r in rows if r["category"] == "NEW_DIFFERENT"]
    parser_fail = [r for r in rows if r["category"] == "PARSER_FAIL"]
    new_extract = [r for r in rows if r["category"] == "NEW_EXTRACT"]

    deltas: list[float] = []
    for r in corrected:
        try:
            deltas.append(abs(float(str(r["delta_pct"]))))
        except ValueError:
            continue

    lines: list[str] = []
    lines.append("# Phase 9.2 02b — Step 1h re-run audit\n")
    lines.append(
        "Re-runs the post-fix AMF parser (`src/ingestion/amf/parser.py`, Steps 1b + 1c) "
        "on every FR `verified_cash` deal and compares the extracted price with the "
        "value currently stored in the DB. **No DB write** — this is the "
        "validation checkpoint before Step 1i applies the corrections.\n"
    )
    lines.append("## 1. Summary\n")
    lines.append(f"- Deals re-parsed: **{total}**")
    if skipped_no_pdf:
        lines.append(f"- Deals where the local PDF was missing: {skipped_no_pdf}")
    lines.append("")
    lines.append("| Category | Count | Share |")
    lines.append("|---|---:|---:|")
    for cat in ("UNCHANGED", "CORRECTED", "NEW_DIFFERENT", "PARSER_FAIL", "NEW_EXTRACT"):
        c = cat_counts.get(cat, 0)
        pct = (100 * c / total) if total else 0
        lines.append(f"| `{cat}` | {c} | {pct:.1f}% |")
    lines.append("")

    if corrected:
        lines.append("### Correction provenance\n")
        lines.append("| Source label | Count |")
        lines.append("|---|---:|")
        for src in sorted(src_counts_corrected):
            lines.append(f"| `{src}` | {src_counts_corrected[src]} |")
        lines.append("")
        if deltas:
            lines.append("### Correction delta (|new - old| / old, %)\n")
            lines.append(f"- count : {len(deltas)}")
            lines.append(f"- min   : {min(deltas):.2f}")
            lines.append(f"- median: {statistics.median(deltas):.2f}")
            lines.append(f"- max   : {max(deltas):.2f}")
            lines.append("")

    lines.append("## 2. Top 20 corrections (by |delta %|)\n")
    if not corrected:
        lines.append(
            "_No CORRECTED rows — the new parser agrees with the DB on every "
            "verified_cash entry._\n"
        )
    else:
        lines.append("| Ref | Target | Old | New | Δ % | Source |")
        lines.append("|---|---|---:|---:|---:|---|")
        for r in _top_corrected(rows):
            lines.append(
                f"| {r['regulator_ref']} | {str(r['target_name'])[:40]} | "
                f"{r['old_offer_price']} | {r['new_offer_price']} | "
                f"{r['delta_pct']} | `{r['new_source']}` |"
            )
        lines.append("")

    lines.append("## 3. NEW_DIFFERENT cases (low-confidence new value — review)\n")
    if not new_different:
        lines.append("_None._\n")
    else:
        lines.append(
            "These rows hit `fallback_first_match` and produced a different "
            "value than the legacy did on the same code path. The new value is "
            "**not** trusted by Step 1i — the user must read the PDF before any "
            "of them is applied to the DB.\n"
        )
        lines.append("| Ref | Target | Old | New | Δ % | Source |")
        lines.append("|---|---|---:|---:|---:|---|")
        for r in new_different:
            lines.append(
                f"| {r['regulator_ref']} | {str(r['target_name'])[:40]} | "
                f"{r['old_offer_price']} | {r['new_offer_price']} | "
                f"{r['delta_pct']} | `{r['new_source']}` |"
            )
        lines.append("")

    lines.append("## 4. PARSER_FAIL cases (new logic returns None)\n")
    if not parser_fail:
        lines.append("_None._\n")
    else:
        lines.append(
            "These rows previously had a stored price; the post-fix parser now "
            "returns None. Every entry is a regression candidate — read the PDF "
            "and decide whether to (a) extend the parser to cover the missing "
            "case, (b) skip from Step 1i, or (c) accept as `suspect_low_unverified`.\n"
        )
        lines.append("| Ref | Target | Old | Notes |")
        lines.append("|---|---|---:|---|")
        for r in parser_fail:
            note = "PDF missing on disk" if not r["pdf_path"] else "regex no longer matches"
            lines.append(
                f"| {r['regulator_ref']} | {str(r['target_name'])[:40]} | "
                f"{r['old_offer_price']} | {note} |"
            )
        lines.append("")

    lines.append("## 5. NEW_EXTRACT cases (parser now finds where old missed)\n")
    if not new_extract:
        lines.append(
            "_None — expected, since the input set is verified_cash (every row "
            "had a stored price)._\n"
        )
    else:
        lines.append("Sample (up to 5):\n")
        lines.append("| Ref | Target | Old | New | Source |")
        lines.append("|---|---|---:|---:|---|")
        for r in new_extract[:5]:
            lines.append(
                f"| {r['regulator_ref']} | {str(r['target_name'])[:40]} | "
                f"(none) | {r['new_offer_price']} | `{r['new_source']}` |"
            )
        lines.append("")

    lines.append("## 6. Recommendation\n")
    if parser_fail or new_extract:
        lines.append(
            "**STOP before Step 1i.** PARSER_FAIL or NEW_EXTRACT rows surfaced — "
            "investigate before any DB write.\n"
        )
    elif new_different:
        lines.append(
            "**STOP before Step 1i.** NEW_DIFFERENT rows surfaced — the user must "
            "manually review each PDF to validate or reject the new value.\n"
        )
    else:
        lines.append(
            "**Proceed to Step 1i.** Every change is a CORRECTED row with a "
            "high-confidence source label. The DB update can safely apply the "
            "`new_offer_price` column to the `CORRECTED` rows transactionally.\n"
        )
    lines.append("")
    lines.append(
        f"_Raw audit CSV: `data/audits/p92_02b_re_run_comparison.csv` (gitignored, "
        f"{total} rows)._"
    )

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def _print_summary(rows: list[dict[str, object]], *, skipped_no_pdf: int) -> None:
    cat_counts = _bucket(rows, "category")
    src_counts_corrected = Counter(
        str(r["new_source"]) for r in rows if r["category"] == "CORRECTED"
    )
    total = len(rows)
    print()
    print("=" * 72)
    print(f"P9.2 02b Step 1h re-run -- {total} FR verified_cash deals")
    print("=" * 72)
    print()
    print("by category:")
    for cat in ("UNCHANGED", "CORRECTED", "NEW_DIFFERENT", "PARSER_FAIL", "NEW_EXTRACT"):
        c = cat_counts.get(cat, 0)
        pct = (100 * c / total) if total else 0
        print(f"  {cat:<16}: {c:>4}  ({pct:.1f}%)")
    if skipped_no_pdf:
        print(f"  (of which PDF-missing: {skipped_no_pdf})")
    print()
    if src_counts_corrected:
        print("CORRECTED by source:")
        for src in sorted(src_counts_corrected):
            print(f"  {src:<32}: {src_counts_corrected[src]}")
        print()
    print(f"CSV : {OUT_CSV}")
    print(f"MD  : {OUT_MD}")


if __name__ == "__main__":
    asyncio.run(_re_run())
