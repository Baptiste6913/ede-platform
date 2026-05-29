"""P9.2 02a end-to-end pipeline integration — parser → service → DB.

These tests exercise the full chain `extract_pdf_metadata` ->
`upsert_deal_from_bdif` the way `BdifPoller.run_once` does (poller.py:113-127),
so the wiring shipped in commit #2 cannot break silently for the live poll.
Unlike the per-method tests in test_service_p92_02a.py, the first two cases
parse real PDFs from the sample (TIPIAK + BALYO) to prove the integration
end-to-end. The remaining cases inject a fabricated `ParsedMetadata` to drive
paths (outlier / pre-existing flag) that have no naturally-occurring fixture.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from src.core.models import Deal
from src.ingestion.amf.bdif_api import (
    BdifDocumentFile,
    BdifItem,
    BdifSociete,
)
from src.ingestion.amf.parser import ParsedMetadata, extract_pdf_metadata
from src.ingestion.amf.service import (
    PARSER_VERSION_02A,
    upsert_deal_from_bdif,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_TIPIAK_PDF = REPO_ROOT / "data" / "pdfs" / "fr" / "2024" / "224C0830.pdf"
FIXTURE_BALYO_PDF = REPO_ROOT / "data" / "pdfs" / "fr" / "2026" / "226C0020.pdf"


def _bdif(numero: str, target: str = "TARGET") -> BdifItem:
    """Minimal BdifItem fixture — only the fields the upsert reads."""
    return BdifItem(
        id=1,
        numero=numero,
        domaine="DOP",
        types_information=("OPA",),
        types_document=("NotesEtAutresInformations",),
        types_operation=("OPA",),
        date_information=datetime(2026, 5, 12, tzinfo=UTC),
        date_publication=datetime(2026, 5, 12, 10, tzinfo=UTC),
        societes=(BdifSociete(jeton="T", raison_sociale=target, role="SocieteVisee"),),
        documents=(
            BdifDocumentFile(
                nom_fichier=f"{numero}.pdf",
                path=f"2026/{numero}/HASH.pdf",
                accessible=True,
            ),
        ),
    )


def _md(price: Decimal | None, *, currency: str | None = "EUR") -> ParsedMetadata:
    return ParsedMetadata(
        deal_type="opa",
        target_name="TARGET",
        acquirer_name=None,
        announcement_date=date(2026, 5, 12),
        offer_price=price,
        currency=currency,
    )


# ---------------- (a) real PDF, extractable price ----------------


async def test_e2e_new_deal_with_pdf_extractable_price(db_session: AsyncSession) -> None:
    """TIPIAK 224C0830 — real PDF, 'prix unitaire de 82 €'. End-to-end:
    parser extracts 82, service classifies verified_cash, deal lands at
    parser_version=2."""
    assert FIXTURE_TIPIAK_PDF.is_file(), "fixture missing: TIPIAK 224C0830.pdf"

    pdf_md = extract_pdf_metadata(FIXTURE_TIPIAK_PDF)
    assert pdf_md.offer_price == Decimal("82")  # sanity on the parser leg

    result = await upsert_deal_from_bdif(
        db_session,
        _bdif("224C0830", "TIPIAK"),
        pdf_path=FIXTURE_TIPIAK_PDF,
        pdf_metadata=pdf_md,
    )
    assert result.created is True

    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price == Decimal("82")
    assert deal.currency == "EUR"
    assert deal.offer_price_quality_flag == "verified_cash"
    assert deal.parser_version == PARSER_VERSION_02A
    assert deal.pdf_path == str(FIXTURE_TIPIAK_PDF)


# ---------------- (b) real PDF, parser silent ----------------


async def test_e2e_new_deal_with_pdf_no_price(db_session: AsyncSession) -> None:
    """BALYO 226C0020 — real PDF without an extractable price (a 'complement
    a D&I' with no offer clause in the first 5 pages). End-to-end:
    parser returns None, service classifies suspect_low_unverified, deal
    still lands at parser_version=2 so the backfill query excludes it next
    run."""
    assert FIXTURE_BALYO_PDF.is_file(), "fixture missing: BALYO 226C0020.pdf"

    pdf_md = extract_pdf_metadata(FIXTURE_BALYO_PDF)
    assert pdf_md.offer_price is None  # sanity on the parser leg

    result = await upsert_deal_from_bdif(
        db_session,
        _bdif("226C0020", "BALYO"),
        pdf_path=FIXTURE_BALYO_PDF,
        pdf_metadata=pdf_md,
    )
    assert result.created is True

    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price is None
    assert deal.offer_price_quality_flag == "suspect_low_unverified"
    assert deal.parser_version == PARSER_VERSION_02A


# ---------------- (c) outlier price ----------------


async def test_e2e_new_deal_with_pdf_outlier_price(db_session: AsyncSession) -> None:
    """An out-of-bounds extraction (NEOEN-OCEANE-class controvalore, modeled
    here as 150 000 €) → failed_validation. Same path as the NEOEN 225C0223
    case that landed failed_validation in the apply summary."""
    result = await upsert_deal_from_bdif(
        db_session,
        _bdif("226C9101", "OUTLIER"),
        pdf_path=None,
        pdf_metadata=_md(Decimal("150000")),
    )
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price == Decimal("150000")
    assert deal.offer_price_quality_flag == "failed_validation"
    assert deal.parser_version == PARSER_VERSION_02A


# ---------------- (d) existing deal at default flag — backfilled ----------------


async def test_e2e_existing_deal_at_default_flag_backfilled(
    db_session: AsyncSession,
) -> None:
    """Legacy state (parser_version=1, default flag, no price). When the
    poller comes back with a parseable PDF, the row is back-filled in
    place — same deal_id, price + flag + parser_version promoted."""
    ref = "226C9102"
    item = _bdif(ref, "LEGACY")

    # Pre-create the legacy row by upserting without pdf_metadata, then force
    # parser_version=1 to simulate a row that pre-dates this pipeline change.
    first = await upsert_deal_from_bdif(db_session, item, pdf_path=None)
    legacy = (await db_session.execute(select(Deal).where(Deal.id == first.deal_id))).scalar_one()
    legacy.parser_version = 1
    await db_session.commit()

    # Now run the pipeline with a parseable price. Existing-deal back-fill
    # path should fire.
    second = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("17")),
    )
    assert second.created is False
    assert second.deal_id == first.deal_id

    await db_session.refresh(legacy)
    assert legacy.offer_price == Decimal("17")
    assert legacy.offer_price_quality_flag == "verified_cash"
    assert legacy.parser_version == PARSER_VERSION_02A


# ---------------- (e) existing deal at verified_cash — not overwritten ----------------


async def test_e2e_existing_deal_at_promoted_flag_not_overwritten(
    db_session: AsyncSession,
) -> None:
    """A deal already promoted (verified_cash, parser_version=2) MUST NOT be
    overwritten when the poll re-fires on the same regulator_ref. This is
    the idempotence guard that lets the live poller co-exist with the
    backfilled corpus."""
    ref = "226C9103"
    item = _bdif(ref, "PROMOTED")

    # Initial pass: lands as verified_cash @ 50.
    first = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("50")),
    )
    assert first.created is True

    # Re-poll: different parser output. Must NOT touch the row.
    second = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("99")),
    )
    assert second.created is False

    deal = (await db_session.execute(select(Deal).where(Deal.id == first.deal_id))).scalar_one()
    await db_session.refresh(deal)
    assert deal.offer_price == Decimal("50")  # frozen at 50, NOT 99
    assert deal.offer_price_quality_flag == "verified_cash"
    assert deal.parser_version == PARSER_VERSION_02A


# ---------------- (f) existing deal at failed_validation — not overwritten ---------


async def test_e2e_existing_deal_at_failed_validation_not_overwritten(
    db_session: AsyncSession,
) -> None:
    """Same protection as (e) for failed_validation rows: once a deal has
    been flagged out-of-bounds (NEOEN-OCEANE-class), the poll cannot un-flag
    it by re-extracting on a noisy second run."""
    ref = "226C9104"
    item = _bdif(ref, "OUTLIER PROMOTED")

    first = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("150000")),
    )
    assert first.created is True
    deal = (await db_session.execute(select(Deal).where(Deal.id == first.deal_id))).scalar_one()
    assert deal.offer_price_quality_flag == "failed_validation"

    # Re-poll with an in-bounds price — MUST be ignored.
    second = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("42")),
    )
    assert second.created is False

    await db_session.refresh(deal)
    assert deal.offer_price == Decimal("150000")  # frozen at 150 000
    assert deal.offer_price_quality_flag == "failed_validation"


# ---------------- (g) pdf_path None handled gracefully ----------------


async def test_e2e_pdf_path_none_handled_gracefully(db_session: AsyncSession) -> None:
    """A BDIF item without a PDF MUST NOT crash the pipeline. The deal is
    created at the default flag — the next poll (or the backfill) will
    re-parse it once the PDF is available."""
    result = await upsert_deal_from_bdif(
        db_session,
        _bdif("226C9105", "NO PDF"),
        pdf_path=None,
        pdf_metadata=None,
    )
    assert result.created is True

    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price is None
    assert deal.offer_price_quality_flag == "suspect_low_unverified"
    assert deal.parser_version == PARSER_VERSION_02A
    assert deal.pdf_path is None
