"""Tests for src.ingestion.consob.parser — Italian regex on synthetic PDFs."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import fitz
import pytest

from src.ingestion.consob.parser import extract_pdf_metadata


def _make_pdf(text: str, *, pages: int = 1) -> bytes:
    doc = fitz.open()
    try:
        for _ in range(pages):
            page = doc.new_page(width=595, height=842)
            page.insert_text((50, 80), text, fontsize=10)
        return doc.tobytes()
    finally:
        doc.close()


@pytest.fixture
def opa_pdf(tmp_path: Path) -> Iterator[Path]:
    text = (
        "DOCUMENTO DI OFFERTA\n"
        "Offerta pubblica di acquisto obbligatoria totalitaria\n"
        "Offerente: Bidder Holding Italia Spa\n"
        "Emittente: Target Italia Spa\n"
        "Il corrispettivo unitario e' pari a Euro 28,50 per azione\n"
        "Periodo di adesione: dal 11 maggio 2026 al 12 giugno 2026\n"
        "Comunicazione n. 23-456 del 5 maggio 2026\n"
    )
    p = tmp_path / "synthetic-it.pdf"
    p.write_bytes(_make_pdf(text))
    yield p


def test_extract_pdf_metadata_pulls_visa_and_dates(opa_pdf: Path) -> None:
    md = extract_pdf_metadata(opa_pdf)
    assert md.official_visa == "Comunicazione n. 23-456"
    assert md.announcement_date == date(2026, 5, 5)
    assert md.opening_date == date(2026, 5, 11)
    assert md.closing_date_est == date(2026, 6, 12)


def test_extract_pdf_metadata_pulls_price(opa_pdf: Path) -> None:
    md = extract_pdf_metadata(opa_pdf)
    assert md.offer_price == Decimal("28.50")
    assert md.currency == "EUR"


def test_extract_pdf_metadata_pulls_parties(opa_pdf: Path) -> None:
    md = extract_pdf_metadata(opa_pdf)
    assert md.offerente_name_from_pdf == "Bidder Holding Italia Spa"
    assert md.target_name_from_pdf == "Target Italia Spa"


def test_extract_pdf_metadata_handles_euro_after_amount(tmp_path: Path) -> None:
    pdf = tmp_path / "p2.pdf"
    pdf.write_bytes(_make_pdf("Prezzo: 1.234,56 EUR per azione"))
    md = extract_pdf_metadata(pdf)
    assert md.offer_price == Decimal("1234.56")
    assert md.currency == "EUR"


def test_extract_pdf_metadata_graceful_on_missing_file(tmp_path: Path) -> None:
    md = extract_pdf_metadata(tmp_path / "does-not-exist.pdf")
    assert md.official_visa is None
    assert md.offer_price is None
    assert md.has_minimum() is False


def test_extract_pdf_metadata_min_when_only_visa_present(tmp_path: Path) -> None:
    pdf = tmp_path / "p3.pdf"
    pdf.write_bytes(_make_pdf("Comunicazione n. 99-1 del 1 gennaio 2026"))
    md = extract_pdf_metadata(pdf)
    assert md.has_minimum() is True
    assert md.official_visa == "Comunicazione n. 99-1"
    assert md.announcement_date == date(2026, 1, 1)
