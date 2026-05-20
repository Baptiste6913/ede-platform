"""Tests for src.ingestion.bafin.parser — German regex on synthetic PDFs."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import fitz
import pytest

from src.ingestion.bafin.parser import extract_pdf_metadata


def _make_pdf(text: str, *, pages: int = 1) -> bytes:
    doc = fitz.open()
    try:
        for _ in range(pages):
            page = doc.new_page(width=595, height=842)
            # Insert in chunks so PyMuPDF respects line breaks.
            page.insert_text((50, 80), text, fontsize=9)
        return doc.tobytes()
    finally:
        doc.close()


@pytest.fixture
def synthetic_pdf(tmp_path: Path) -> Iterator[Path]:
    text = (
        "Pflichtangebot nach §§ 35 Abs. 2, 14 WpUEG\n"
        "Bieter: ACME Bidco GmbH, München\n"
        "Zielgesellschaft: Foo AG, Frankfurt am Main\n"
        "Annahmefrist: vom 01. März 2026 bis zum 30. April 2026\n"
        "Angebotspreis: EUR 28,50 je Aktie\n"
    )
    p = tmp_path / "synthetic.pdf"
    p.write_bytes(_make_pdf(text))
    yield p


def test_extract_pdf_metadata_finds_annahmefrist_with_german_months(
    synthetic_pdf: Path,
) -> None:
    md = extract_pdf_metadata(synthetic_pdf)
    assert md.opening_date == date(2026, 3, 1)
    assert md.closing_date_est == date(2026, 4, 30)


def test_extract_pdf_metadata_finds_price_eur(synthetic_pdf: Path) -> None:
    md = extract_pdf_metadata(synthetic_pdf)
    assert md.offer_price == Decimal("28.50")
    assert md.currency == "EUR"


def test_extract_pdf_metadata_finds_bieter_target_offer_type(
    synthetic_pdf: Path,
) -> None:
    md = extract_pdf_metadata(synthetic_pdf)
    assert md.bieter_name_from_pdf is not None
    assert "ACME Bidco GmbH" in md.bieter_name_from_pdf
    assert md.target_name_from_pdf is not None
    assert "Foo AG" in md.target_name_from_pdf
    assert md.offer_type_from_pdf == "Pflichtangebot"


def test_extract_pdf_metadata_handles_dotted_dates(tmp_path: Path) -> None:
    text = (
        "Übernahmeangebot\n"
        "Bieter: Foo GmbH\n"
        "Zielgesellschaft: Bar SE\n"
        "Annahmefrist Beginn: 15.06.2026 Ende: 14.07.2026\n"
        "Angebotspreis 12,00 EUR\n"
    )
    p = tmp_path / "dotted.pdf"
    p.write_bytes(_make_pdf(text))
    md = extract_pdf_metadata(p)
    assert md.opening_date == date(2026, 6, 15)
    assert md.closing_date_est == date(2026, 7, 14)
    assert md.offer_price == Decimal("12.00")


def test_extract_pdf_metadata_returns_empty_on_unreadable_pdf(tmp_path: Path) -> None:
    p = tmp_path / "broken.pdf"
    p.write_bytes(b"%PDF-1.4 not actually a valid pdf body")
    md = extract_pdf_metadata(p)
    assert md.opening_date is None
    assert md.offer_price is None
    assert md.bieter_name_from_pdf is None
    assert md.has_minimum() is False


def test_extract_pdf_metadata_has_minimum_when_any_field_present() -> None:
    from src.ingestion.bafin.parser import ParsedBafinMetadata

    md = ParsedBafinMetadata(
        opening_date=date(2026, 1, 1),
        closing_date_est=None,
        offer_price=None,
        currency=None,
        target_name_from_pdf=None,
        bieter_name_from_pdf=None,
        offer_type_from_pdf=None,
    )
    assert md.has_minimum() is True
