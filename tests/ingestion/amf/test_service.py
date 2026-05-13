"""Tests for src.ingestion.amf.service — BDIF upsert + RSS event recording."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from src.core.models import Deal, Event
from src.ingestion.amf.bdif_api import (
    BdifDocumentFile,
    BdifItem,
    BdifSociete,
)
from src.ingestion.amf.rss_watcher import RssItem
from src.ingestion.amf.service import (
    record_rss_event,
    upsert_deal_from_bdif,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


def _bdif(
    *,
    numero: str = "226C0644",
    target: str = "FNAC DARTY",
    initiateur: str | None = None,
    op: str = "OPA",
) -> BdifItem:
    societes = [BdifSociete(jeton="T", raison_sociale=target, role="SocieteVisee")]
    if initiateur:
        societes.append(BdifSociete(jeton="I", raison_sociale=initiateur, role="Initiateur"))
    return BdifItem(
        id=42,
        numero=numero,
        domaine="DOP",
        types_information=("OPA",),
        types_document=("NotesEtAutresInformations",),
        types_operation=(op,),
        date_information=datetime(2026, 5, 12, tzinfo=UTC),
        date_publication=datetime(2026, 5, 12, 10, tzinfo=UTC),
        societes=tuple(societes),
        documents=(
            BdifDocumentFile(
                nom_fichier=f"{numero}.pdf",
                path=f"2026/{numero}/HASH.pdf",
                accessible=True,
            ),
        ),
    )


def _rss(
    title: str = "L'AMF enjoint à FOO de déposer projet OPA visant BAR - AMF-2026-D-0421",
    ref: str | None = "AMF-2026-D-0421",
    link: str = "https://www.amf-france.org/fr/details/AMF-2026-D-0421",
) -> RssItem:
    return RssItem(
        title=title,
        link=link,
        summary="",
        published=datetime(2026, 5, 12, 9, 0, tzinfo=UTC),
        regulator_ref=ref,
    )


# ---------------- upsert_deal_from_bdif ----------------


async def test_upsert_bdif_creates_deal_with_canonical_ref(
    db_session: AsyncSession,
) -> None:
    item = _bdif(initiateur="GIE FNAC DARTY HOLDING")
    result = await upsert_deal_from_bdif(db_session, item, pdf_path=None)
    assert result.created is True

    deal = (
        await db_session.execute(select(Deal).where(Deal.regulator_ref == "226C0644"))
    ).scalar_one()
    assert deal.juridiction == "FR"
    assert deal.target_name == "FNAC DARTY"
    assert deal.acquirer_name == "GIE FNAC DARTY HOLDING"
    assert deal.deal_type == "opa"
    assert "AMF-SYN-" not in deal.regulator_ref


async def test_upsert_bdif_emits_filing_event_with_full_payload(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    item = _bdif()
    fake_pdf = tmp_path / "226C0644.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    await upsert_deal_from_bdif(db_session, item, pdf_path=fake_pdf)

    events = (await db_session.execute(select(Event))).scalars().all()
    assert len(events) == 1
    e = events[0]
    assert e.event_type == "filing_amf"
    payload = e.raw_payload or {}
    assert payload["source"] == "bdif"
    assert payload["has_document"] is True
    assert payload["numero"] == "226C0644"
    assert payload["types_operation"] == ["OPA"]
    assert any(s["role"] == "SocieteVisee" for s in payload["societes"])


async def test_upsert_bdif_is_idempotent_on_duplicate_numero(
    db_session: AsyncSession,
) -> None:
    item = _bdif()
    first = await upsert_deal_from_bdif(db_session, item, pdf_path=None)
    second = await upsert_deal_from_bdif(db_session, item, pdf_path=None)
    assert first.created is True
    assert second.created is False
    assert second.deal_id == first.deal_id
    events = (await db_session.execute(select(Event))).scalars().all()
    assert len(events) == 1


async def test_upsert_bdif_promotes_pdf_path_on_dedup(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Existing deal without PDF should get its pdf_path filled on rerun."""
    item = _bdif()
    first = await upsert_deal_from_bdif(db_session, item, pdf_path=None)
    pdf = tmp_path / "X.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    await upsert_deal_from_bdif(db_session, item, pdf_path=pdf)
    deal = (await db_session.execute(select(Deal).where(Deal.id == first.deal_id))).scalar_one()
    assert deal.pdf_path == str(pdf)


async def test_upsert_bdif_rejects_empty_numero(db_session: AsyncSession) -> None:
    item = _bdif(numero="")
    with pytest.raises(ValueError, match="numero"):
        await upsert_deal_from_bdif(db_session, item, pdf_path=None)


# ---------------- record_rss_event ----------------


async def test_rss_event_skipped_when_no_canonical_ref(db_session: AsyncSession) -> None:
    item = _rss(ref=None)
    result = await record_rss_event(db_session, item)
    assert result.emitted is False
    assert result.reason == "no_ref"
    assert (await db_session.execute(select(Event))).scalars().all() == []


async def test_rss_event_skipped_when_no_matching_deal(db_session: AsyncSession) -> None:
    item = _rss(ref="AMF-2026-D-9999")
    result = await record_rss_event(db_session, item)
    assert result.emitted is False
    assert result.reason == "unmatched"
    assert (await db_session.execute(select(Event))).scalars().all() == []


async def test_rss_event_emitted_when_ref_matches_existing_bdif_deal(
    db_session: AsyncSession,
) -> None:
    ref = "AMF-2026-D-0421"
    bdif = _bdif(numero=ref, target="ENTREPRENDRE")
    await upsert_deal_from_bdif(db_session, bdif, pdf_path=None)

    result = await record_rss_event(db_session, _rss(ref=ref))
    assert result.emitted is True
    assert result.reason == "created"

    events = (await db_session.execute(select(Event).order_by(Event.id))).scalars().all()
    assert len(events) == 2  # one filing from BDIF + one from RSS
    rss_event = events[-1]
    assert (rss_event.raw_payload or {})["source"] == "rss_display_23"
    assert (rss_event.raw_payload or {})["has_document"] is False


async def test_rss_event_deduplicates_on_same_link(db_session: AsyncSession) -> None:
    ref = "AMF-2026-D-0421"
    await upsert_deal_from_bdif(db_session, _bdif(numero=ref), pdf_path=None)
    item = _rss(ref=ref)

    first = await record_rss_event(db_session, item)
    second = await record_rss_event(db_session, item)
    assert first.emitted is True
    assert second.emitted is False
    assert second.reason == "duplicate"
