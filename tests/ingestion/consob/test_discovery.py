"""Tests for src.ingestion.consob.discovery — HTML extraction on the
captured Step-0 fixture (50 real Consob rows)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.ingestion.consob.discovery import (
    ITALIAN_TYPE_RULES,
    OpaRecord,
    _classify_deal_type,
    _derive_consob_ref,
    parse_listing,
)

CONSOB_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "consob" / "documenti-opa-page1.html"
)


@pytest.fixture
def page1_html() -> str:
    return CONSOB_FIXTURE.read_text(encoding="utf-8")


def test_parse_listing_extracts_50_rows(page1_html: str) -> None:
    records = parse_listing(page1_html, page_number=1)
    assert len(records) == 50
    for r in records:
        assert isinstance(r, OpaRecord)
        assert r.consob_ref.startswith("CONSOB-")
        assert r.page_number == 1


def test_parse_listing_finds_fnac_darty_equivalent_first_row(page1_html: str) -> None:
    """First row in the Step-0 capture was Banca CF+ → Banca Sistema (OPAS)."""
    records = parse_listing(page1_html)
    first = records[0]
    assert first.period_start == date(2026, 5, 11)
    assert first.period_end == date(2026, 6, 12)
    assert first.target_name == "Banca Sistema Spa"
    assert first.offerente_name == "Banca CF+ Credito Fondiario Spa"
    assert first.deal_type == "opas"  # "acquisto e scambio"
    assert first.documento_offerta_url is not None
    assert "opa_bancasistema_20260511.pdf" in first.documento_offerta_url
    assert first.consob_ref == "CONSOB-opa_bancasistema_20260511"


def test_parse_listing_classifies_volontaria_parziale_for_cir(page1_html: str) -> None:
    """Second fixture row: Cir Spa — OPA volontaria parziale."""
    records = parse_listing(page1_html)
    cir = next(r for r in records if r.offerente_name and "Cir" in r.offerente_name)
    assert cir.deal_type == "opa_volontaire_parziale"
    assert cir.period_start == date(2026, 4, 27)


def test_parse_listing_classifies_obbligatoria_for_oep_danzig(page1_html: str) -> None:
    records = parse_listing(page1_html)
    danzig = next(r for r in records if r.target_name and "Digital Value" in r.target_name)
    assert danzig.deal_type == "opa_obligatoire"
    # Danzig fixture has BOTH a documento d'offerta + a comunicato proroga
    assert any("proroga" in label.lower() for label, _ in danzig.additional_links)


def test_parse_listing_every_row_has_documento_offerta_url(page1_html: str) -> None:
    records = parse_listing(page1_html)
    rows_with_doc = sum(1 for r in records if r.documento_offerta_url)
    assert rows_with_doc == 50  # Step-0 finding: all 50 carry a Documento d'offerta


def test_parse_listing_empty_on_missing_ul() -> None:
    assert parse_listing("<html><body>nothing</body></html>") == []


# -------------------------- classifier unit tests --------------------------


@pytest.mark.parametrize(
    ("narrative", "expected"),
    [
        ("Offerta pubblica di acquisto obbligatoria totalitaria", "opa_obligatoire"),
        ("Offerta pubblica di acquisto volontaria totalitaria", "opa_volontaire_totalitaria"),
        ("Offerta pubblica di acquisto volontaria parziale", "opa_volontaire_parziale"),
        ("Offerta pubblica di acquisto e scambio obbligatoria", "opas"),
        ("Offerta pubblica di scambio volontaria totalitaria", "opas"),
        ("Offerta pubblica di acquisto residuale", "opa_obligatoire"),
        ("Offerta volontaria preventiva totalitaria", "opa_volontaire_totalitaria"),
        ("Offerta pubblica di acquisto di consolidamento", "opa_consolidamento"),
    ],
)
def test_classifier_maps_italian_to_canonical(narrative: str, expected: str) -> None:
    assert _classify_deal_type(narrative) == expected


def test_classifier_returns_none_on_unrelated_text() -> None:
    assert _classify_deal_type("Comunicato stampa generico AMF") is None


def test_italian_type_rules_use_canonical_enum_values() -> None:
    """Every mapping target must exist in src.core.enums.DEAL_TYPES."""
    from src.core.enums import DEAL_TYPES

    canonical = set(DEAL_TYPES)
    for _, target in ITALIAN_TYPE_RULES:
        assert target in canonical, f"{target!r} not in DEAL_TYPES"


# -------------------------- consob_ref derivation --------------------------


def test_derive_ref_from_pdf_url_uses_filename_slug() -> None:
    url = (
        "https://www.consob.it/documents/11973/11173223/opa_unicredit_20250215.pdf/"
        "abc-1234?version=1.0&t=12345&download=false"
    )
    ref = _derive_consob_ref(
        url,
        fallback_target=None,
        fallback_offerente=None,
        fallback_start=None,
    )
    assert ref == "CONSOB-opa_unicredit_20250215"


def test_derive_ref_falls_back_to_slug_when_no_pdf() -> None:
    ref = _derive_consob_ref(
        None,
        fallback_target="Banca Generali S.p.A.",
        fallback_offerente="Mediobanca S.p.A.",
        fallback_start=date(2026, 4, 15),
    )
    assert ref is not None
    assert ref.startswith("CONSOB-")
    assert "banca-generali" in ref
    assert "mediobanca" in ref
    assert "20260415" in ref


def test_derive_ref_returns_none_when_nothing_to_hash() -> None:
    assert (
        _derive_consob_ref(None, fallback_target=None, fallback_offerente=None, fallback_start=None)
        is None
    )


# -------------------------- name trimming (narrative-leak defense) --------------------------


def test_trim_company_name_cuts_on_first_comma_marker() -> None:
    """Narrative-leak case found in Step-9 live run: target_name was
    receiving the full sentence past the company name."""
    from src.ingestion.consob.discovery import _trim_company_name

    raw = "Tinexta Spa , ad un corrispettivo unitario pari a 15,00 euro cum dividendo"
    assert _trim_company_name(raw) == "Tinexta Spa"


def test_trim_company_name_cuts_on_rappresentative_marker() -> None:
    from src.ingestion.consob.discovery import _trim_company_name

    raw = (
        "Almawave Spa , rappresentative del 21,05% del capitale sociale "
        "dell'Emittente, corrispondenti alla totalità"
    )
    assert _trim_company_name(raw) == "Almawave Spa"


def test_trim_company_name_caps_at_120_chars() -> None:
    from src.ingestion.consob.discovery import _COMPANY_NAME_MAX_LEN, _trim_company_name

    raw = "Z" * 500
    assert len(_trim_company_name(raw)) == _COMPANY_NAME_MAX_LEN


# -------------------------- since cutoff (12-month window) --------------------------


async def test_iter_all_stops_when_all_rows_older_than_since(page1_html: str) -> None:
    """When `since` is set to a future date, every fixture row is filtered
    out and the iterator must stop on the first page."""
    from collections.abc import AsyncIterator
    from datetime import date as _date

    import httpx

    from src.ingestion.consob.discovery import ConsobDiscoveryClient
    from src.core.scrapingbee_client import ScrapingBeeClient

    pages: dict[str, int] = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        pages["n"] += 1
        return httpx.Response(
            200, text=page1_html, headers={"Spb-Cost": "1", "Spb-Initial-Status-Code": "200"}
        )

    # No DB needed — patch out the budget check.
    class _NullSB:
        async def get(self, target_url: str, **_: object) -> object:  # type: ignore[no-untyped-def]
            resp = handler(httpx.Request("GET", target_url))
            from src.core.scrapingbee_client import ScrapingBeeResponse

            return ScrapingBeeResponse(
                status_code=200,
                text=resp.text,
                content=resp.content,
                credits_cost=1,
                target_url=target_url,
            )

    client = ConsobDiscoveryClient(_NullSB())  # type: ignore[arg-type]
    out: list[object] = []

    async def _drain(it: AsyncIterator[object]) -> None:
        async for r in it:
            out.append(r)

    # since = far future → every row filtered out
    await _drain(client.iter_all(max_pages=3, since=_date(2099, 1, 1)))
    assert out == []
    assert pages["n"] == 1  # stopped after first page
    _ = ScrapingBeeClient  # keep import used
