"""AMF-specific test fixtures: synthetic PDFs and HTTPX mock transport."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "amf"


@pytest.fixture
def rss_sample_bytes() -> bytes:
    return (FIXTURES_DIR / "rss-sample.xml").read_bytes()


@pytest.fixture
def amf_detail_page_html() -> str:
    return (FIXTURES_DIR / "amf-detail-page.html").read_text(encoding="utf-8")


def _make_pdf(text: str, *, pages: int) -> bytes:
    """Generate a small in-memory PDF with the given text replicated per page."""
    doc = fitz.open()
    try:
        for _ in range(pages):
            page = doc.new_page(width=595, height=842)  # A4
            page.insert_text((50, 80), text, fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()


@pytest.fixture
def synthetic_pdf_bytes() -> bytes:
    """A 3-page PDF mimicking a French OPA note d'information cover.

    Uses ASCII-only characters: PyMuPDF's default 'helv' font cannot render
    most non-ASCII glyphs and would silently drop them, breaking the parser
    tests. The parser's regexes accept both accented and non-accented forms.
    """
    cover_text = (
        "Note d'information\n"
        "Projet d'offre publique d'achat visant les actions de la societe Algol SA\n"
        "Initiateur: Bidder Holding France\n"
        "Societe visee: Algol SA\n"
        "Prix de l'offre: 28,50 EUR\n"
        "Date de depot: 12 mai 2025\n"
        "Numero: AMF-2025-D-0421\n"
    )
    return _make_pdf(cover_text, pages=3)


@pytest.fixture
def synthetic_pdf_path(tmp_path: Path, synthetic_pdf_bytes: bytes) -> Iterator[Path]:
    p = tmp_path / "amf-test.pdf"
    p.write_bytes(synthetic_pdf_bytes)
    yield p
