"""Tests for :func:`src.pricing.acquirer_registry.resolve_acquirer`.

The inputs are the raw acquirer strings the BaFin parser actually extracts from
the Commerzbank / ProSieben PDFs (see ``tests/fixtures/p91a/*_excerpt.txt``).
"""

from __future__ import annotations

from src.pricing.acquirer_registry import resolve_acquirer


def test_resolve_unicredit_from_commerzbank_pdf_string():
    info = resolve_acquirer("UniCredit S.p.A.")
    assert info is not None
    assert info.isin == "IT0005239360"
    assert info.ticker_yf == "UCG.MI"


def test_resolve_mfe_from_prosieben_pdf_string():
    info = resolve_acquirer("MFE-MEDIAFOREUROPE N.V.")
    assert info is not None
    assert info.isin == "NL0015001OI1"
    assert info.ticker_yf == "MFEA.MI"


def test_resolve_unknown_returns_none():
    assert resolve_acquirer("Some Unknown Bidder AG") is None
