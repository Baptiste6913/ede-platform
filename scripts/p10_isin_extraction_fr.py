"""P10 Step 1 — extract the target ISIN from AMF BDIF PDFs and back-fill
``deals.ticker_target`` for every FR labelled deal that currently has no
ticker.

Anchor strategy
---------------
AMF BDIF PDFs carry the target ISIN twice on the cover page:

- in the document reference header (``<ref>-<ISIN>-OP<n>-...``),
- in the running header at the top of every page (same shape).

The FIRST FR-prefixed ISIN occurring in the first 2 pages is therefore
the target — no need to disambiguate against the acquirer (which is
usually a holding without an ISIN on the AMF docs).

Validation
----------
- 12-char ISO 6166 format: 2 letters (country), 9 alphanumerics,
  1 digit check (regex below; the actual check-digit is not validated
  — the regex shape + the FR prefix gate is enough on the corpus).
- Must start with ``FR``.

Outputs
-------
- ``data/audits/p10_isin_extraction_fr.csv`` (gitignored) — one row per
  deal with status (`applied` / `skipped_no_pdf` / `skipped_no_isin` /
  `skipped_pdf_error`).
- ``docs/phase-10/isin_extraction_fr_audit.md`` (tracked) — synthesis.

Mode
----
- default (no flag) = DRY-RUN, computes & reports nothing in DB.
- ``--apply`` commits ``UPDATE deals SET ticker_target = <ISIN>`` per
  deal in a single transaction.

Idempotent: a re-run skips any deal that already has ``ticker_target``
non-null.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # PyMuPDF
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal
from src.core.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = REPO_ROOT / "data" / "audits" / "p10_isin_extraction_fr.csv"
OUT_MD = REPO_ROOT / "docs" / "phase-10" / "isin_extraction_fr_audit.md"

# Strict ISIN shape: 2 country letters + 9 alphanumeric + 1 digit. The check
# digit is not Luhn-validated — the FR-prefix filter below is enough.
_ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b")
_FR_PREFIX = "FR"

# Max PDF pages to scan for the target ISIN. The AMF running header lives at
# the top of every page, so the cover page alone is enough; 2 pages is a
# safety margin for filings whose cover page wraps differently.
_MAX_PAGES = 2


def _local_pdf(stored: str | None) -> Path | None:
    if not stored:
        return None
    rel = stored.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO_ROOT / rel
    return candidate if candidate.is_file() else None


def _extract_isin(pdf_path: Path) -> tuple[str | None, str]:
    """Return ``(isin, status)`` where status is one of
    ``"ok"`` / ``"pdf_error:<ExcType>"`` / ``"no_isin"``."""
    try:
        pieces: list[str] = []
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                if i >= _MAX_PAGES:
                    break
                pieces.append(page.get_text("text") or "")
        text = "\n".join(pieces)
    except Exception as exc:
        return (None, f"pdf_error:{type(exc).__name__}")

    for m in _ISIN_RE.finditer(text):
        candidate = m.group(1)
        if candidate.startswith(_FR_PREFIX):
            return (candidate, "ok")
    return (None, "no_isin")


async def _process(*, dry_run: bool) -> None:
    engine = create_async_engine(get_settings().database_url, echo=False, future=True)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"[STEP-1] mode: {mode}")

    rows: list[dict[str, str]] = []
    applied = 0
    skipped = 0

    async with sm() as session:
        # Scope: FR labelled deals whose ticker_target is still NULL.
        deals = (
            (
                await session.execute(
                    select(Deal)
                    .where(
                        Deal.juridiction == "FR",
                        Deal.completion_label.isnot(None),
                        Deal.ticker_target.is_(None),
                    )
                    .order_by(Deal.id)
                )
            )
            .scalars()
            .all()
        )
        total = len(deals)
        print(f"[STEP-1] {total} FR labelled deals to process")

        for idx, deal in enumerate(deals, start=1):
            deal_id = deal.id
            ref = deal.regulator_ref
            target = deal.target_name
            pdf = _local_pdf(deal.pdf_path)
            if pdf is None:
                rows.append(_row(deal_id, ref, target, None, "skipped_no_pdf"))
                skipped += 1
                continue
            isin, status = _extract_isin(pdf)
            if isin is None:
                rows.append(_row(deal_id, ref, target, None, f"skipped_{status}"))
                skipped += 1
                continue

            if not dry_run:
                await session.execute(
                    update(Deal).where(Deal.id == deal_id).values(ticker_target=isin)
                )
            rows.append(_row(deal_id, ref, target, isin, "applied"))
            applied += 1
            if idx % 25 == 0:
                print(f"[STEP-1] progress: {idx}/{total} (last status={status})")

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()
    _write_csv(rows)
    _write_md(rows, applied=applied, skipped=skipped, total=len(rows))

    print()
    print(f"applied : {applied}")
    print(f"skipped : {skipped}")
    print(f"CSV     : {OUT_CSV}")
    print(f"MD      : {OUT_MD}")


def _row(deal_id: int, ref: str, target: str, isin: str | None, status: str) -> dict[str, str]:
    return {
        "deal_id": str(deal_id),
        "regulator_ref": ref,
        "target_name": target,
        "isin": isin or "",
        "status": status,
    }


def _write_csv(rows: list[dict[str, str]]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["deal_id", "regulator_ref", "target_name", "isin", "status"]
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_md(rows: list[dict[str, str]], *, applied: int, skipped: int, total: int) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(r["status"] for r in rows)
    success_pct = 100.0 * applied / total if total else 0.0

    lines: list[str] = []
    lines.append("# Phase 10 Step 1 — ISIN extraction FR audit\n")
    lines.append(
        "Anchor on the first FR-prefixed ISIN occurring in the first 2 pages "
        "of each AMF BDIF PDF. Persisted to `deals.ticker_target` for every "
        "FR labelled deal that previously carried no ticker. Idempotent — "
        "re-running this script skips deals whose `ticker_target` is already "
        "set.\n"
    )
    lines.append("## Summary\n")
    lines.append(f"- Deals processed : **{total}**")
    lines.append(f"- ISIN found + applied : **{applied}** ({success_pct:.1f}%)")
    lines.append(f"- Skipped : {skipped}")
    lines.append("")
    lines.append("### Status distribution\n")
    lines.append("| Status | Count |")
    lines.append("|---|---:|")
    for st in sorted(status_counts):
        lines.append(f"| `{st}` | {status_counts[st]} |")
    lines.append("")

    failed = [r for r in rows if r["status"] != "applied"]
    if failed:
        lines.append("## Skipped / failed cases\n")
        lines.append("| Ref | Target | Status |")
        lines.append("|---|---|---|")
        for r in failed:
            lines.append(f"| {r['regulator_ref']} | {r['target_name'][:50]} | `{r['status']}` |")
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="P10 Step 1 ISIN extraction FR")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Commit the UPDATEs. Without this flag, the script runs as a DRY-RUN.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_process(dry_run=not args.apply))
