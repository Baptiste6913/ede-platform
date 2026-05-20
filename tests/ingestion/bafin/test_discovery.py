"""Tests for src.ingestion.bafin.discovery — HTML extraction on the
captured Step-0 fixture (240 real BaFin rows, 2016-2026)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.ingestion.bafin.discovery import (
    GERMAN_TYPE_RULES,
    AngebotsunterlageRecord,
    _classify_deal_type,
    _derive_bafin_ref,
    _normalize_isin,
    _trim_company_name,
    parse_listing,
)

BAFIN_FIXTURE = (
    Path(__file__).resolve().parents[2] / "fixtures" / "bafin" / "angebotsunterlagen-listing.html"
)


@pytest.fixture
def listing_html() -> str:
    return BAFIN_FIXTURE.read_text(encoding="utf-8")


# -------------------------- end-to-end listing parse --------------------------


def test_parse_listing_extracts_many_rows(listing_html: str) -> None:
    records = parse_listing(listing_html)
    # 241 rows on the page, minus 9 Untersagung filtered out = 232 expected.
    assert len(records) >= 200
    assert len(records) <= 241
    for r in records:
        assert isinstance(r, AngebotsunterlageRecord)
        assert r.bafin_ref.startswith("BAFIN-")
        assert r.wrapper_url.startswith("https://www.bafin.de")


def test_parse_listing_first_row_is_unicredit_commerzbank(listing_html: str) -> None:
    records = parse_listing(listing_html)
    first = records[0]
    assert "UniCredit" in first.bieter_name
    assert "COMMERZBANK" in first.target_name
    assert first.target_isin == "DE000CBK1001"
    assert first.deal_type == "opa_volontaire_totalitaria"  # Übernahmeangebot
    assert first.veroeffentlichung_date == date(2026, 5, 5)
    assert first.bafin_ref == "BAFIN-DE000CBK1001-20260505"
    assert "commerzbank" in first.wrapper_url.lower()


def test_parse_listing_ingests_untersagung_as_prohibition(listing_html: str) -> None:
    """Phase-6 Step-0 extension: Untersagung rows previously filtered are
    now ingested as `prohibition_ungenutzt` so they can be used as
    label=0 training examples for the scoring model."""
    records = parse_listing(listing_html)
    untersagung_rows = [r for r in records if "untersagung" in r.offer_type_raw.lower()]
    # The captured fixture has 9 Untersagung rows per Step-0 audit.
    assert len(untersagung_rows) >= 5
    assert all(r.deal_type == "prohibition_ungenutzt" for r in untersagung_rows)


def test_parse_listing_maps_delisting_variants_to_delisting_offer(
    listing_html: str,
) -> None:
    records = parse_listing(listing_html)
    delisting_rows = [r for r in records if "delisting" in r.offer_type_raw.lower()]
    assert len(delisting_rows) >= 50  # Step-0 found 76 total
    assert all(r.deal_type == "delisting_offer" for r in delisting_rows)


def test_parse_listing_classifies_pflichtangebot(listing_html: str) -> None:
    records = parse_listing(listing_html)
    pflicht = [r for r in records if r.offer_type_raw == "Pflichtangebot"]
    assert len(pflicht) >= 10
    assert all(r.deal_type == "opa_obligatoire" for r in pflicht)


def test_parse_listing_classifies_uebernahmeangebot(listing_html: str) -> None:
    records = parse_listing(listing_html)
    uebern = [r for r in records if r.offer_type_raw == "Übernahmeangebot"]
    assert len(uebern) >= 50
    assert all(r.deal_type == "opa_volontaire_totalitaria" for r in uebern)


def test_parse_listing_empty_on_missing_table() -> None:
    assert parse_listing("<html><body>nothing</body></html>") == []


# -------------------------- classifier unit tests --------------------------


@pytest.mark.parametrize(
    ("narrative", "expected"),
    [
        ("Übernahmeangebot", "opa_volontaire_totalitaria"),
        ("Pflichtangebot", "opa_obligatoire"),
        ("Erwerbsangebot", "opa_volontaire_parziale"),
        ("Teilerwerbsangebot", "opa_volontaire_parziale"),
        ("Delisting-Erwerbsangebot", "delisting_offer"),
        ("Delisting-Übernahmeangebot", "delisting_offer"),
        ("Delisting-Pflichtangebot", "delisting_offer"),
        ("Delisting-Rückerwerbsangebot", "delisting_offer"),
        ("Pflichtangebot / Erwerbsangebot", "opa_obligatoire"),
        ("Erwerbsangebot Änderung", "opa_volontaire_parziale"),
        # Phase-6 Step-0 extension — Untersagung now ingested.
        ("Untersagung", "prohibition_ungenutzt"),
    ],
)
def test_classifier_maps_german_to_canonical(narrative: str, expected: str) -> None:
    assert _classify_deal_type(narrative) == expected


def test_classifier_returns_none_on_unknown_narrative() -> None:
    assert _classify_deal_type("Some unknown communication") is None


def test_classifier_rules_use_canonical_enum_values() -> None:
    """Every mapping target must exist in src.core.enums.DEAL_TYPES."""
    from src.core.enums import DEAL_TYPES

    canonical = set(DEAL_TYPES)
    for _, target in GERMAN_TYPE_RULES:
        assert target in canonical, f"{target!r} not in DEAL_TYPES"


# -------------------------- ISIN normalisation --------------------------


def test_normalize_isin_strips_spaces() -> None:
    assert _normalize_isin("DE000 CBK1001") == "DE000CBK1001"


def test_normalize_isin_rejects_malformed() -> None:
    assert _normalize_isin("not-an-isin") is None
    assert _normalize_isin("DE000") is None  # too short


# -------------------------- ref derivation --------------------------


def test_derive_ref_uses_isin_when_available() -> None:
    ref = _derive_bafin_ref(
        isin="DE000CBK1001",
        when=date(2026, 5, 5),
        fallback="https://example.com/foo.html",
    )
    assert ref == "BAFIN-DE000CBK1001-20260505"


def test_derive_ref_falls_back_to_slug_when_no_isin() -> None:
    ref = _derive_bafin_ref(
        isin=None,
        when=date(2026, 4, 20),
        fallback="https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/foo_bar.html?nn=1",
    )
    assert ref == "BAFIN-foo_bar-20260420"


# -------------------------- name trimming --------------------------


def test_trim_company_name_strips_trailing_punct() -> None:
    assert _trim_company_name("ACME GmbH ,") == "ACME GmbH"


def test_trim_company_name_cuts_on_vertreten_marker() -> None:
    raw = "Foo AG vertreten durch den Vorstand der Bar GmbH"
    assert _trim_company_name(raw) == "Foo AG"


def test_trim_company_name_caps_at_120_chars() -> None:
    raw = "Z" * 500
    assert len(_trim_company_name(raw)) == 120
