"""P9.2 02a integration — wiring of `extract_pdf_metadata` through
`upsert_deal_from_bdif` and derivation of `offer_price_quality_flag`.

Covers both the new-deal path (pdf_metadata populates the row) and the
existing-deal path (idempotent back-fill only when the current flag is still
the migration-0015 default `suspect_low_unverified`). The two spotlighted
boundary cases — LV GROUP 10 000 € (small-cap retrait, in-bounds) and NEOEN
OCEANE 101 382 € (controvalore artefact, out-of-bounds) — are exercised
explicitly so the AMF bound [0.01, 100000] cannot drift without breaking a
test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from src.core.models import Deal
from src.ingestion.amf.bdif_api import (
    BdifDocumentFile,
    BdifItem,
    BdifSociete,
)
from src.ingestion.amf.parser import ParsedMetadata
from src.ingestion.amf.service import (
    PARSER_VERSION_02A,
    upsert_deal_from_bdif,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _bdif(numero: str, target: str) -> BdifItem:
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
    """Build a minimal ParsedMetadata fixture with only the price-relevant
    fields set."""
    return ParsedMetadata(
        deal_type="opa",
        target_name="TARGET",
        acquirer_name=None,
        announcement_date=date(2026, 5, 12),
        offer_price=price,
        currency=currency,
    )


# ---------------- new-deal path ----------------


async def test_upsert_populates_offer_price_when_metadata_provided(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """A fresh deal with parser output landing in-bounds → verified_cash,
    price + currency + parser_version stamped."""
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    item = _bdif("226C9001", "PRODWARE")
    result = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=pdf,
        pdf_metadata=_md(Decimal("28")),
    )
    assert result.created is True

    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price == Decimal("28")
    assert deal.currency == "EUR"
    assert deal.offer_price_quality_flag == "verified_cash"
    assert deal.parser_version == PARSER_VERSION_02A


async def test_upsert_routes_outlier_to_failed_validation(
    db_session: AsyncSession,
) -> None:
    """A price above 100 000 (the AMF upper bound) → failed_validation flag.
    150 000 is the synthetic outlier — same code path as a NEOEN OCEANE
    101 382 controvalore artefact."""
    item = _bdif("226C9002", "OUTLIER")
    result = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("150000")),
    )
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price == Decimal("150000")
    assert deal.offer_price_quality_flag == "failed_validation"
    assert deal.parser_version == PARSER_VERSION_02A


async def test_upsert_routes_lv_group_10000_to_verified_cash(
    db_session: AsyncSession,
) -> None:
    """LV GROUP 222C0375 — real 10 000 € retrait price on a radiated small-cap
    (Finexsi-validated). MUST land verified_cash with the widened upper bound
    of 100 000. Pins the boundary so a future tighten of the bound breaks
    this case on purpose."""
    item = _bdif("222C0375", "LV GROUP")
    result = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("10000")),
    )
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price == Decimal("10000")
    assert deal.offer_price_quality_flag == "verified_cash"


async def test_upsert_routes_neoen_oceane_101382_to_failed_validation(
    db_session: AsyncSession,
) -> None:
    """NEOEN OCEANE controvalore 101 382 € — the NBSP fix from commit #1 makes
    this number parseable, and the 100 000 upper bound MUST then reject it as
    not-an-offer-price. Pins the upper bound so a future widening to >= 101 382
    breaks this case on purpose."""
    item = _bdif("226C9003", "NEOEN OCEANE")
    result = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("101382")),
    )
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price == Decimal("101382")
    assert deal.offer_price_quality_flag == "failed_validation"


async def test_upsert_routes_null_to_suspect_low_unverified(
    db_session: AsyncSession,
) -> None:
    """Parser silent (offer_price=None) → suspect_low_unverified, same value
    as the migration-0015 server default so the back-fill path can identify
    'never parsed' rows."""
    item = _bdif("226C9004", "SILENT")
    result = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(None),
    )
    deal = (await db_session.execute(select(Deal).where(Deal.id == result.deal_id))).scalar_one()
    assert deal.offer_price is None
    assert deal.offer_price_quality_flag == "suspect_low_unverified"


# ---------------- existing-deal idempotent back-fill ----------------


async def test_existing_deal_backfilled_when_default_flag(
    db_session: AsyncSession,
) -> None:
    """An existing deal whose flag is still the default suspect_low_unverified
    MUST be back-filled on re-run when pdf_metadata is provided."""
    item = _bdif("226C9005", "BACKFILL TARGET")

    # First pass: no PDF, no metadata → row sits at the default flag.
    first = await upsert_deal_from_bdif(db_session, item, pdf_path=None)
    assert first.created is True
    deal = (await db_session.execute(select(Deal).where(Deal.id == first.deal_id))).scalar_one()
    assert deal.offer_price is None
    assert deal.offer_price_quality_flag == "suspect_low_unverified"

    # Second pass: PDF metadata now available → back-fill kicks in.
    second = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("42.50")),
    )
    assert second.created is False
    assert second.deal_id == first.deal_id

    await db_session.refresh(deal)
    assert deal.offer_price == Decimal("42.50")
    assert deal.offer_price_quality_flag == "verified_cash"
    assert deal.parser_version == PARSER_VERSION_02A


async def test_existing_deal_not_overwritten_when_flag_promoted(
    db_session: AsyncSession,
) -> None:
    """An existing deal whose flag has already been promoted (verified_cash,
    failed_validation, manual_review, etc.) MUST NOT be overwritten on re-run
    — the back-fill is strictly bounded to the default-flag class. This is
    the idempotence guard that lets the poller be re-run safely."""
    item = _bdif("226C9006", "ALREADY PROMOTED")

    # First pass: in-bounds price → row is promoted to verified_cash @ 50.
    first = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("50")),
    )
    assert first.created is True

    # Second pass: different (lower) price → MUST be ignored. The row keeps
    # the promoted value and the promoted flag.
    second = await upsert_deal_from_bdif(
        db_session,
        item,
        pdf_path=None,
        pdf_metadata=_md(Decimal("30")),
    )
    assert second.created is False

    deal = (await db_session.execute(select(Deal).where(Deal.id == first.deal_id))).scalar_one()
    await db_session.refresh(deal)
    assert deal.offer_price == Decimal("50")  # NOT overwritten to 30
    assert deal.offer_price_quality_flag == "verified_cash"
