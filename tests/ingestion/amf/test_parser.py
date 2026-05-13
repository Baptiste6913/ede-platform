"""Tests for src.ingestion.amf.parser."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from src.ingestion.amf.parser import (
    extract_pdf_metadata,
    merge,
    parse_title,
)


def test_parse_title_recognises_opa() -> None:
    md = parse_title(
        "Dépôt d'un projet d'offre publique d'achat visant les actions de la société Algol SA"
    )
    assert md.deal_type == "opa"
    assert md.target_name == "Algol SA"


def test_parse_title_recognises_garantie_de_cours() -> None:
    md = parse_title("Garantie de cours visant les actions de Beta France SA")
    assert md.deal_type == "garantie_de_cours"


def test_parse_title_recognises_ope() -> None:
    md = parse_title("Note d'information OPE visant les titres Gamma Industries")
    assert md.deal_type == "ope"
    assert md.target_name == "Gamma Industries"


def test_parse_title_promotes_opa_when_obligatoire_keyword() -> None:
    md = parse_title("OPA obligatoire sur Delta Pharma")
    assert md.deal_type == "opa_obligatoire"


def test_parse_title_recognises_opra() -> None:
    assert parse_title("OPRA initiée par X").deal_type == "opra"


def test_parse_title_recognises_opr_ro() -> None:
    assert parse_title("OPR-RO sur Omega SA").deal_type == "opr_ro"


def test_parse_title_returns_none_when_no_keyword() -> None:
    md = parse_title("Communiqué AMF sur les frais de gestion")
    assert md.deal_type is None
    assert md.has_minimum() is False


def test_extract_pdf_metadata_pulls_price_and_date(synthetic_pdf_path: Path) -> None:
    md = extract_pdf_metadata(synthetic_pdf_path)
    assert md.deal_type == "opa"
    assert md.target_name == "Algol SA"
    assert md.acquirer_name == "Bidder Holding France"
    assert md.announcement_date == date(2025, 5, 12)
    assert md.offer_price == Decimal("28.50")
    assert md.currency == "EUR"


def test_extract_pdf_metadata_graceful_on_missing_file(tmp_path: Path) -> None:
    """Bogus path: should log + return empty metadata, never raise."""
    md = extract_pdf_metadata(tmp_path / "does-not-exist.pdf")
    assert md.deal_type is None
    assert md.target_name is None
    assert md.offer_price is None


def test_merge_title_wins_on_deal_type_and_target() -> None:
    title_md = parse_title("OPA visant les actions de la société Algol SA")
    pdf_md = extract_pdf_metadata
    # Fake a PDF result with different values
    from src.ingestion.amf.parser import ParsedMetadata

    pdf_md = ParsedMetadata(
        deal_type="ope",
        target_name="Different SA",
        acquirer_name="Bidder Holding France",
        announcement_date=date(2025, 5, 12),
        offer_price=Decimal("28.50"),
        currency="EUR",
    )
    merged = merge(title_md, pdf_md)
    assert merged.deal_type == "opa"  # title wins
    assert merged.target_name == "Algol SA"  # title wins
    assert merged.acquirer_name == "Bidder Holding France"  # pdf fills
    assert merged.announcement_date == date(2025, 5, 12)
    assert merged.offer_price == Decimal("28.50")
    assert merged.currency == "EUR"


def test_merge_pdf_fallback_when_title_empty() -> None:
    from src.ingestion.amf.parser import ParsedMetadata

    title_md = ParsedMetadata(
        deal_type=None,
        target_name=None,
        acquirer_name=None,
        announcement_date=None,
        offer_price=None,
        currency=None,
    )
    pdf_md = ParsedMetadata(
        deal_type="opa",
        target_name="From PDF SA",
        acquirer_name=None,
        announcement_date=date(2025, 1, 1),
        offer_price=Decimal("10.00"),
        currency="EUR",
    )
    merged = merge(title_md, pdf_md)
    assert merged.deal_type == "opa"
    assert merged.target_name == "From PDF SA"
    assert merged.offer_price == Decimal("10.00")
