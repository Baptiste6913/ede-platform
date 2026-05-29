"""P9.2 02a [Step 0 B] — extended dry-run of the AMF parser on 80 FR deals.

Stratified sample: 16 deals per announcement-year (2022-2026), including
the 10 deals already audited in P9.2 Step 0 (continuity). The rest are
deterministic-random per year (seed = 920).

For each deal we:
- run `amf_parser.extract_pdf_metadata` on the local PDF,
- capture (offer_price, currency, target_name, acquirer_name,
  announcement_date) from the parser,
- compute a heuristic `doc_type` (note d'information / response_note /
  complement / conformity_decision / procedural_other) by scanning the
  first ~500 chars of raw text,
- compute a `status` (extracted_in_bounds / extracted_out_of_bounds /
  silent_miss / parser_exception).

Output: data/audits/p92_02a_amf_dryrun_extended.csv (80 rows).
"""

from __future__ import annotations

import asyncio
import csv
import logging
import random
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog

logging.basicConfig(level=logging.ERROR)
structlog.configure(
    processors=[structlog.processors.KeyValueRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
)

from sqlalchemy import select

from src.core.db import dispose_engine, get_sessionmaker
from src.core.models import Deal
from src.ingestion.amf.parser import extract_pdf_metadata

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "audits"
OUT_SAMPLE = OUT_DIR / "p92_02a_sample.csv"
OUT_DRYRUN = OUT_DIR / "p92_02a_amf_dryrun_extended.csv"

SAMPLE_PER_YEAR = 16
YEARS = (2022, 2023, 2024, 2025, 2026)
SEED = 920

# Step 0 P9.2 already-audited refs (carry-over for continuity)
STEP0_REFS = {
    "216C1735",
    "219C0051",
    "223C0044",
    "224C0830",
    "224C0915",
    "225C0021",
    "225C0741",
    "225C0921",
    "225C2081",
    "225C2156",
}


def _local_pdf(stored_path: str) -> Path | None:
    rel = stored_path.replace("/repo/", "", 1).lstrip("/")
    candidate = REPO / rel
    return candidate if candidate.is_file() else None


# AMF document-type codes embedded in the page-1 header line
# `<ref>-<ISIN>-OP<n>-<code>`.
# A* (A01, A06, ...) = "Avis" — conformity decision (price restated).
# AS* (AS01, AS03, AS06, ...) = "Avis Simplifié" — deposit notice / initial filing.
# R* (R06, R08, ...) = "Retrait" — OPR conformity (price restated).
# C* = "Communiqué" — supplementary / complement (price usually not restated).
_HEADER_CODE_RE = re.compile(
    r"\b\d{3}C\d{4}-[A-Z]{2}[A-Z0-9]{9}[0-9]-OP\d{3,4}-(?P<code>[A-Z]{1,3}\d{2})\b"
)


def _normalize_apostrophes(s: str) -> str:
    # AMF PDFs use typographic curly apostrophes (U+2019). Normalize to ASCII
    # so the substring heuristics below can match.
    return s.replace("’", "'").replace("ʼ", "'")


def _classify_doc_type(text: str) -> str:
    """Heuristic doc-type classifier on the first ~600 chars of page 1.

    Combines two signals:
    1. The AMF header-code suffix (A* / AS* / R* / C*) when extractable.
    2. The textual title (Décision de conformité / Dépôt d'un projet…).

    AMF publishes 4-6 doc types per deal; only ~2 carry the price.
    """
    head_raw = text[:800]
    head = _normalize_apostrophes(head_raw).lower()

    # Pass 1 — title-based (most reliable when present)
    if "décision" in head and ("conformité" in head or "conformite" in head):
        return "conformity_decision"
    if "dépôt d'un projet d'offre" in head or "depot d'un projet d'offre" in head:
        return "deposit_notice"
    if "complément à d&i" in head or "complement a d&i" in head:
        return "complement"
    if "projet de note en réponse" in head or "projet de note en reponse" in head:
        return "response_note"
    if (
        "calendrier" in head
        or "résultat de l'offre" in head
        or "resultat de l'offre" in head
        or "ouverture de l'offre" in head
    ):
        return "procedural_other"

    # Pass 2 — header code fallback
    m = _HEADER_CODE_RE.search(head_raw)
    if m:
        code = m.group("code")
        if code.startswith("AS"):
            return "deposit_notice_byheader"
        if code.startswith("R"):
            return "conformity_decision_byheader"
        if code.startswith("A"):
            return "conformity_decision_byheader"
        if code.startswith("C"):
            return "complement_byheader"
    return "other"


def _classify_status(offer_price: Decimal | None) -> str:
    if offer_price is None:
        return "silent_miss"
    # Wide preliminary bounds just to flag obvious outliers; final calibration
    # happens in the synthesis step.
    if offer_price < Decimal("0.01") or offer_price > Decimal("1000000"):
        return "extracted_out_of_bounds"
    return "extracted_in_bounds"


async def _sample() -> list[Deal]:
    sm = get_sessionmaker()
    picked: list[Deal] = []
    async with sm() as session:
        # Pull every FR deal once, partition by year.
        all_fr = (
            (await session.execute(select(Deal).where(Deal.juridiction == "FR").order_by(Deal.id)))
            .scalars()
            .all()
        )

        # Carry-over Step 0 deals first
        step0_deals = [d for d in all_fr if d.regulator_ref in STEP0_REFS]
        carried_refs = {d.regulator_ref for d in step0_deals}
        picked.extend(step0_deals)

        # Group remaining by announcement-year
        by_year: dict[int, list[Deal]] = {}
        for d in all_fr:
            if d.regulator_ref in carried_refs:
                continue
            by_year.setdefault(d.announcement_date.year, []).append(d)

        rng = random.Random(SEED)
        for year in YEARS:
            year_carryover = sum(1 for d in step0_deals if d.announcement_date.year == year)
            need = SAMPLE_PER_YEAR - year_carryover
            pool = by_year.get(year, [])
            if len(pool) <= need:
                # Year too sparse — take all remaining for that year.
                picked.extend(pool)
            else:
                picked.extend(rng.sample(pool, need))

    return picked


async def main() -> None:
    deals = await _sample()
    print(f"Sampled {len(deals)} deals")

    sample_rows: list[dict[str, object]] = []
    dryrun_rows: list[dict[str, object]] = []

    for deal in deals:
        local = _local_pdf(deal.pdf_path or "")
        sample_rows.append(
            {
                "deal_id": deal.id,
                "regulator_ref": deal.regulator_ref,
                "target_name": deal.target_name,
                "announcement_date": deal.announcement_date.isoformat(),
                "year": deal.announcement_date.year,
                "deal_type": deal.deal_type,
                "from_step0": deal.regulator_ref in STEP0_REFS,
                "pdf_path": deal.pdf_path,
                "pdf_local_exists": local is not None,
            }
        )

        if local is None:
            dryrun_rows.append(
                {
                    "deal_id": deal.id,
                    "regulator_ref": deal.regulator_ref,
                    "target_name": deal.target_name,
                    "year": deal.announcement_date.year,
                    "doc_type": "unknown_missing_pdf",
                    "offer_price": "",
                    "currency": "",
                    "parser_target": "",
                    "parser_acquirer": "",
                    "parser_date": "",
                    "status": "missing_pdf",
                }
            )
            continue

        try:
            md = extract_pdf_metadata(local, max_pages=5)
            text = md.raw_text_sample or ""
            doc_type = _classify_doc_type(text)
            status = _classify_status(md.offer_price)
            dryrun_rows.append(
                {
                    "deal_id": deal.id,
                    "regulator_ref": deal.regulator_ref,
                    "target_name": deal.target_name,
                    "year": deal.announcement_date.year,
                    "doc_type": doc_type,
                    "offer_price": str(md.offer_price) if md.offer_price is not None else "",
                    "currency": md.currency or "",
                    "parser_target": md.target_name or "",
                    "parser_acquirer": md.acquirer_name or "",
                    "parser_date": md.announcement_date.isoformat() if md.announcement_date else "",
                    "status": status,
                }
            )
        except Exception as exc:
            dryrun_rows.append(
                {
                    "deal_id": deal.id,
                    "regulator_ref": deal.regulator_ref,
                    "target_name": deal.target_name,
                    "year": deal.announcement_date.year,
                    "doc_type": "exception",
                    "offer_price": "",
                    "currency": "",
                    "parser_target": "",
                    "parser_acquirer": "",
                    "parser_date": "",
                    "status": f"parser_exception:{type(exc).__name__}",
                }
            )

    await dispose_engine()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_SAMPLE.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(sample_rows[0].keys()))
        writer.writeheader()
        writer.writerows(sample_rows)
    with OUT_DRYRUN.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(dryrun_rows[0].keys()))
        writer.writeheader()
        writer.writerows(dryrun_rows)

    # Console summaries
    by_status: dict[str, int] = {}
    by_doctype: dict[str, int] = {}
    by_year: dict[int, int] = {}
    for r in dryrun_rows:
        by_status[str(r["status"])] = by_status.get(str(r["status"]), 0) + 1
        by_doctype[str(r["doc_type"])] = by_doctype.get(str(r["doc_type"]), 0) + 1
        by_year[int(r["year"])] = by_year.get(int(r["year"]), 0) + 1

    print("\n=== Distribution by status ===")
    for k, v in sorted(by_status.items()):
        print(f"  {k:<32}: {v}")
    print("\n=== Distribution by doc_type ===")
    for k, v in sorted(by_doctype.items()):
        print(f"  {k:<32}: {v}")
    print("\n=== Distribution by year ===")
    for k, v in sorted(by_year.items()):
        print(f"  {k}: {v}")
    print(f"\nSample CSV : {OUT_SAMPLE}")
    print(f"Dryrun CSV : {OUT_DRYRUN}")


if __name__ == "__main__":
    asyncio.run(main())
