"""End-to-end integration test for BdifPoller (HTTP mocked, real DB)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.models import Deal, Event
from src.ingestion.amf.bdif_poller import BdifPoller
from src.ingestion.amf.rate_limiter import RateLimiter

if TYPE_CHECKING:
    pass

BDIF_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "amf" / "bdif"

pytestmark = pytest.mark.integration


def _load(name: str) -> dict:
    return json.loads((BDIF_FIXTURES / name).read_text(encoding="utf-8"))


def _make_pdf_bytes() -> bytes:
    """Minimal valid PDF — just enough for the >1024 bytes guard."""
    import fitz

    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text(
            (50, 50),
            "Fnac Darty - Note d'information OPA 226C0644\nInitiateur: GIE FNAC DARTY",
            fontsize=11,
        )
        return doc.tobytes()
    finally:
        doc.close()


def _bdif_transport(
    page_payload: dict,
    pdf_bytes: bytes,
) -> httpx.MockTransport:
    """Router: /informations -> page_payload, /documents/... -> pdf_bytes."""

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "/back/api/v1/informations" in url:
            offset = int(req.url.params.get("From", 0))
            size = int(req.url.params.get("Size", 50))
            # Slice the fixture to simulate pagination.
            full = page_payload["result"]
            total = page_payload.get("total", len(full))
            return httpx.Response(
                200,
                json={
                    "total": total,
                    "result": full[offset : offset + size],
                    "aggregations": page_payload.get("aggregations", {}),
                },
            )
        if "/back/api/v1/documents/" in url:
            return httpx.Response(
                200,
                content=pdf_bytes,
                headers={"content-type": "application/pdf"},
            )
        return httpx.Response(404, text="not found")

    return httpx.MockTransport(handler)


async def test_bdif_poller_creates_deals_with_pdfs(
    db_engine: object,
    db_clean: None,
    tmp_path: Path,
) -> None:
    _ = db_clean
    page = _load("page_1_opa_notes.json")
    pdf = _make_pdf_bytes()

    client = httpx.AsyncClient(transport=_bdif_transport(page, pdf))
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    rl = RateLimiter(100.0)
    poller = BdifPoller(
        client=client,
        rate_limiter=rl,
        session_factory=session_factory,
        data_dir=str(tmp_path),
        max_items=5,
    )

    try:
        result = await poller.run_once()
    finally:
        await poller.aclose()

    # 5 fixture items, all with documents → 5 created, 5 PDFs downloaded.
    assert result.discovered == 5
    assert result.created == 5
    assert result.skipped == 0
    assert result.pdf_downloaded == 5
    assert result.pdf_failed == 0

    # PDFs landed on disk under data_dir/pdfs/fr/2026/{numero}.pdf
    pdf_dir = tmp_path / "pdfs" / "fr" / "2026"
    assert pdf_dir.is_dir()
    pdfs = sorted(p.name for p in pdf_dir.glob("*.pdf"))
    assert "226C0644.pdf" in pdfs  # Fnac Darty
    assert len(pdfs) == 5

    # DB: 5 deals with canonical refs, all linked to a single filing_amf event each.
    async with session_factory() as s:
        deals = (await s.execute(select(Deal).where(Deal.juridiction == "FR"))).scalars().all()
        assert len(deals) == 5
        fnac = next(d for d in deals if d.regulator_ref == "226C0644")
        assert fnac.target_name == "FNAC DARTY"
        assert fnac.deal_type == "opa"
        assert fnac.pdf_path is not None
        assert "226C0644.pdf" in fnac.pdf_path
        assert "AMF-SYN-" not in fnac.regulator_ref  # no synthetic refs

        events = (await s.execute(select(Event))).scalars().all()
        assert len(events) == 5
        assert all(e.event_type == "filing_amf" for e in events)
        fnac_event = next(e for e in events if e.deal_id == fnac.id)
        payload = fnac_event.raw_payload or {}
        assert payload["source"] == "bdif"
        assert payload["has_document"] is True
        assert payload["numero"] == "226C0644"


async def test_bdif_poller_is_idempotent_on_second_run(
    db_engine: object,
    db_clean: None,
    tmp_path: Path,
) -> None:
    _ = db_clean
    page = _load("page_1_opa_notes.json")
    pdf = _make_pdf_bytes()
    client = httpx.AsyncClient(transport=_bdif_transport(page, pdf))
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    rl = RateLimiter(100.0)
    poller = BdifPoller(
        client=client,
        rate_limiter=rl,
        session_factory=session_factory,
        data_dir=str(tmp_path),
        max_items=5,
    )

    try:
        first = await poller.run_once()
        second = await poller.run_once()
    finally:
        await poller.aclose()

    assert first.created == 5
    assert second.created == 0
    assert second.skipped == 5
    # No duplicate event emission.
    async with session_factory() as s:
        events = (await s.execute(select(Event))).scalars().all()
        assert len(events) == 5


async def test_bdif_poller_continues_on_pdf_failure(
    db_engine: object,
    db_clean: None,
    tmp_path: Path,
) -> None:
    """A 500 on one PDF must not block insert of the deal nor other items."""
    _ = db_clean
    page = _load("page_1_opa_notes.json")

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "/back/api/v1/informations" in url:
            offset = int(req.url.params.get("From", 0))
            size = int(req.url.params.get("Size", 50))
            return httpx.Response(
                200,
                json={
                    "total": page["total"],
                    "result": page["result"][offset : offset + size],
                    "aggregations": page.get("aggregations", {}),
                },
            )
        if "/back/api/v1/documents/" in url:
            # 500 always — every PDF download fails after retries.
            return httpx.Response(500, text="boom")
        return httpx.Response(404)

    # Make retries fast.
    from unittest.mock import AsyncMock, patch

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    rl = RateLimiter(100.0)
    poller = BdifPoller(
        client=client,
        rate_limiter=rl,
        session_factory=session_factory,
        data_dir=str(tmp_path),
        max_items=5,
    )

    try:
        with patch("src.ingestion.amf.rate_limiter.asyncio.sleep", new=AsyncMock()):
            result = await poller.run_once()
    finally:
        await poller.aclose()

    # 5 deals created, but 0 PDFs (all failed).
    assert result.discovered == 5
    assert result.created == 5
    assert result.pdf_downloaded == 0
    assert result.pdf_failed == 5
    async with session_factory() as s:
        deals = (await s.execute(select(Deal))).scalars().all()
        assert all(d.pdf_path is None for d in deals)
        # Event still emitted, marked as has_document=False
        events = (await s.execute(select(Event))).scalars().all()
        assert all((e.raw_payload or {})["has_document"] is False for e in events)
