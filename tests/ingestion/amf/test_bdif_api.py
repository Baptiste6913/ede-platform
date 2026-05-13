"""Tests for src.ingestion.amf.bdif_api — parse + filter + paginate."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from src.ingestion.amf.bdif_api import (
    BDIF_BASE_URL,
    OPERATION_TO_DEAL_TYPE,
    BdifApiClient,
    BdifItem,
    parse_item,
)
from src.ingestion.amf.rate_limiter import RateLimiter

BDIF_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "amf" / "bdif"


@pytest.fixture
def page_opa_notes() -> dict:
    return json.loads((BDIF_FIXTURES / "page_1_opa_notes.json").read_text(encoding="utf-8"))


@pytest.fixture
def page_opa() -> dict:
    return json.loads((BDIF_FIXTURES / "page_1_opa.json").read_text(encoding="utf-8"))


@pytest.fixture
def page_default() -> dict:
    return json.loads((BDIF_FIXTURES / "page_1_default.json").read_text(encoding="utf-8"))


def test_parse_item_extracts_core_fields(page_opa_notes: dict) -> None:
    raw = page_opa_notes["result"][2]  # Fnac Darty entry, see fixture
    assert raw["numero"] == "226C0644"
    item = parse_item(raw)
    assert item.numero == "226C0644"
    assert item.types_information == ("OPA",)
    # Fnac Darty fixture carries both NotesEtAutresInformations and Decisions tags
    assert "NotesEtAutresInformations" in item.types_document
    assert item.primary_operation == "OPA"
    assert item.deal_type == "opa"
    assert item.target_name == "FNAC DARTY"
    assert item.acquirer_name is None  # not present in this fixture
    assert item.announcement_date == date(2026, 5, 12)
    assert item.first_pdf is not None
    assert item.first_pdf.absolute_url.startswith(
        "https://bdif.amf-france.org/back/api/v1/documents/2026/226C0644/"
    )


def test_parse_item_maps_all_operations() -> None:
    """Every typesOperation value in OPERATION_TO_DEAL_TYPE produces a deal_type."""
    for raw_op, expected in OPERATION_TO_DEAL_TYPE.items():
        item = parse_item(
            {
                "id": 1,
                "numero": "TEST",
                "typesOperation": [raw_op],
                "documents": [],
                "societes": [],
            }
        )
        assert item.deal_type == expected, f"{raw_op} -> {item.deal_type}"


def test_parse_item_handles_missing_optional_fields() -> None:
    item = parse_item({"id": 1, "numero": "X"})
    assert item.numero == "X"
    assert item.deal_type is None
    assert item.target_name is None
    assert item.first_pdf is None
    assert item.announcement_date is None


def test_parse_item_prefers_societevisee_over_societeconcernee() -> None:
    item = parse_item(
        {
            "numero": "X",
            "societes": [
                {"jeton": "A", "raisonSociale": "ALPHA", "role": "SocieteConcernee"},
                {"jeton": "B", "raisonSociale": "BETA", "role": "SocieteVisee"},
            ],
        }
    )
    assert item.target_name == "BETA"


def test_parse_item_picks_initiateur_for_acquirer() -> None:
    item = parse_item(
        {
            "numero": "X",
            "societes": [
                {"jeton": "T", "raisonSociale": "TARGET", "role": "SocieteVisee"},
                {"jeton": "I", "raisonSociale": "INITIATEUR", "role": "Initiateur"},
            ],
        }
    )
    assert item.acquirer_name == "INITIATEUR"


def _mock_transport(handler) -> httpx.MockTransport:  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


async def test_search_page_sends_repeated_query_keys(page_opa_notes: dict) -> None:
    """typesInformation, typesDocument, typesOperation must be repeated query keys."""
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json=page_opa_notes)

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        api = BdifApiClient(client, RateLimiter(100.0))
        items, total = await api.search_page(
            types_information=("OPA",),
            types_document=("NotesEtAutresInformations",),
            offset=0,
            size=5,
        )
    assert total == page_opa_notes["total"]
    assert len(items) == len(page_opa_notes["result"])
    assert "FNAC DARTY" in {i.target_name for i in items if i.target_name}

    assert len(captured) == 1
    qs = captured[0].url.params
    assert qs["From"] == "0"
    assert qs["Size"] == "5"
    assert qs["typesInformation"] == "OPA"
    assert qs["typesDocument"] == "NotesEtAutresInformations"


async def test_search_page_sends_required_headers(page_opa_notes: dict) -> None:
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(200, json=page_opa_notes)

    async with httpx.AsyncClient(
        transport=_mock_transport(handler),
        headers={
            "User-Agent": "EDE-Bot/test",
            "Accept-Language": "fr-FR,fr;q=0.9",
        },
    ) as client:
        api = BdifApiClient(client, RateLimiter(100.0))
        await api.search_page(offset=0, size=5)

    assert len(captured) == 1
    req = captured[0]
    assert req.headers["accept"] == "application/json"
    assert req.headers["referer"] == f"{BDIF_BASE_URL}/fr"
    assert req.headers["accept-language"] == "fr-FR,fr;q=0.9"


async def test_iter_all_paginates_until_exhausted() -> None:
    """iter_all keeps fetching until a partial page or `total` is reached."""
    # Fake API: 7 items total, page size 3 → pages of 3, 3, 1.
    items_payload = [
        {"id": i, "numero": f"REF{i}", "documents": [], "societes": []} for i in range(7)
    ]
    call_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        offset = int(req.url.params["From"])
        size = int(req.url.params["Size"])
        return httpx.Response(
            200,
            json={
                "total": len(items_payload),
                "result": items_payload[offset : offset + size],
                "aggregations": {},
            },
        )

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        api = BdifApiClient(client, RateLimiter(100.0))
        seen: list[BdifItem] = [item async for item in api.iter_all(page_size=3)]

    assert [i.numero for i in seen] == [f"REF{i}" for i in range(7)]
    assert call_count["n"] == 3  # 3+3+1


async def test_iter_all_respects_max_items() -> None:
    items_payload = [
        {"id": i, "numero": f"X{i}", "documents": [], "societes": []} for i in range(50)
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        offset = int(req.url.params["From"])
        size = int(req.url.params["Size"])
        return httpx.Response(
            200,
            json={
                "total": 50,
                "result": items_payload[offset : offset + size],
                "aggregations": {},
            },
        )

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        api = BdifApiClient(client, RateLimiter(100.0))
        collected = [item async for item in api.iter_all(page_size=20, max_items=12)]
    assert len(collected) == 12


async def test_search_page_raises_on_non_dict_json() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    from src.core.exceptions import ExternalServiceError

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        api = BdifApiClient(client, RateLimiter(100.0), max_retries=0)
        with pytest.raises(ExternalServiceError):
            await api.search_page()
