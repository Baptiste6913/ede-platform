"""Tests for the RSS event-only AmfPoller (post-phase-3 routing)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.models import Deal, Event
from src.ingestion.amf.bdif_api import (
    BdifDocumentFile,
    BdifItem,
    BdifSociete,
)
from src.ingestion.amf.poller import AmfPoller
from src.ingestion.amf.rate_limiter import RateLimiter
from src.ingestion.amf.service import upsert_deal_from_bdif

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.integration

_RSS_THAT_MENTIONS_KNOWN_REF = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AMF</title>
    <link>https://www.amf-france.org/fr</link>
    <description>test</description>
    <item>
      <title>L'AMF enjoint DANAE GROUP de déposer un OPA - AMF-2026-D-0421</title>
      <link>https://www.amf-france.org/fr/actualites/AMF-2026-D-0421</link>
      <description><![CDATA[OPA imposée]]></description>
      <pubDate>Wed, 13 May 2026 14:00:00 +0200</pubDate>
    </item>
    <item>
      <title>Communiqué OPRA non liée à un deal connu - AMF-2099-Z-0000</title>
      <link>https://www.amf-france.org/fr/actualites/AMF-2099-Z-0000</link>
      <description><![CDATA[]]></description>
      <pubDate>Wed, 13 May 2026 15:00:00 +0200</pubDate>
    </item>
    <item>
      <title>Cartographie 2026 des marchés (mentionne offre publique mais sans ref)</title>
      <link>https://www.amf-france.org/fr/cartographie-2026</link>
      <description><![CDATA[]]></description>
      <pubDate>Wed, 13 May 2026 16:00:00 +0200</pubDate>
    </item>
  </channel>
</rss>
""".encode()


def _bdif(numero: str, target: str = "DANAE TARGET") -> BdifItem:
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
                path=f"2026/{numero}/X.pdf",
                accessible=True,
            ),
        ),
    )


async def test_rss_poller_emits_event_for_matching_ref(
    db_engine: object,
    db_clean: None,
) -> None:
    _ = db_clean
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]

    # Seed an existing BDIF-sourced deal with ref AMF-2026-D-0421.
    async with session_factory() as s:
        await upsert_deal_from_bdif(s, _bdif("AMF-2026-D-0421"), pdf_path=None)

    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=_RSS_THAT_MENTIONS_KNOWN_REF)
    )
    client = httpx.AsyncClient(transport=transport, base_url="https://test.local")
    rl = RateLimiter(100.0)
    poller = AmfPoller(client=client, rate_limiter=rl, session_factory=session_factory)
    poller._rss_watcher._rate_limiter = rl

    try:
        result = await poller.run_once()
    finally:
        await poller.aclose()

    # 3 RSS items match the regex; 1 has a known ref (the DANAE one), 1 has
    # an unknown ref (AMF-2099-Z-0000), 1 has no canonical ref.
    assert result.matched == 3
    assert result.events_emitted == 1
    assert result.unmatched == 1
    assert result.no_ref == 1
    assert result.duplicates == 0

    async with session_factory() as s:
        deals = (await s.execute(select(Deal))).scalars().all()
        # Only the BDIF-sourced deal exists — RSS doesn't create deals.
        assert len(deals) == 1
        events = (
            (await s.execute(select(Event).where(Event.deal_id == deals[0].id))).scalars().all()
        )
        # 1 filing event from BDIF upsert + 1 from RSS link to known ref.
        assert len(events) == 2


async def test_rss_poller_idempotent_on_second_run(
    db_engine: object,
    db_clean: None,
) -> None:
    _ = db_clean
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    async with session_factory() as s:
        await upsert_deal_from_bdif(s, _bdif("AMF-2026-D-0421"), pdf_path=None)

    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=_RSS_THAT_MENTIONS_KNOWN_REF)
    )
    client = httpx.AsyncClient(transport=transport, base_url="https://test.local")
    rl = RateLimiter(100.0)
    poller = AmfPoller(client=client, rate_limiter=rl, session_factory=session_factory)
    poller._rss_watcher._rate_limiter = rl

    try:
        first = await poller.run_once()
        second = await poller.run_once()
    finally:
        await poller.aclose()

    assert first.events_emitted == 1
    assert second.events_emitted == 0
    assert second.duplicates == 1


async def test_rss_poller_creates_no_synthetic_deals(
    db_engine: object,
    db_clean: None,
) -> None:
    """Phase 3 guarantee: AmfPoller never creates new deal rows."""
    _ = db_clean
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]

    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=_RSS_THAT_MENTIONS_KNOWN_REF)
    )
    client = httpx.AsyncClient(transport=transport, base_url="https://test.local")
    rl = RateLimiter(100.0)
    poller = AmfPoller(client=client, rate_limiter=rl, session_factory=session_factory)
    poller._rss_watcher._rate_limiter = rl

    try:
        result = await poller.run_once()
    finally:
        await poller.aclose()

    assert result.events_emitted == 0  # no seed deal — every match is unmatched/no_ref
    async with session_factory() as s:
        deals = (await s.execute(select(Deal))).scalars().all()
        assert deals == []
