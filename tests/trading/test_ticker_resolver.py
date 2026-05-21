"""Unit tests for the ticker resolver (pure — no IBKR/DB)."""

from __future__ import annotations

import pytest

from src.trading.ticker_resolver import (
    DEFAULT_MAPPING_PATH,
    ResolvedTicker,
    TickerResolver,
    extract_isin,
    normalize_name,
)

MAPPING = {
    "Commerzbank": {"symbol": "CBK", "exchange": "IBIS", "currency": "EUR"},
    "Digital Value Spa": {"symbol": "DGV", "exchange": "BVME", "currency": "EUR"},
}


# ----------------------------------------------------------------- normalize
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("COMMERZBANK Aktiengesellschaft", "COMMERZBANK"),
        ("Digital Value Spa", "DIGITAL VALUE"),
        ("Klöckner & Co SE", "KL CKNER CO"),
        ("Mediobanca-Banca di Credito Finanziario", "MEDIOBANCA BANCA DI CREDITO FINANZIARIO"),
        ("Next Re SIIQ Spa", "NEXT RE"),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


# -------------------------------------------------------------------- isin
def test_extract_isin_from_bafin_ref():
    assert extract_isin("BAFIN-DE000CBK1001-20260505") == "DE000CBK1001"


def test_extract_isin_prefers_first_candidate():
    assert extract_isin(None, "226C0538", "DE0007257503") == "DE0007257503"


def test_extract_isin_none_when_absent():
    assert extract_isin("226C0538", "opa_simplifiee", None) is None


# --------------------------------------------------------------- resolution
def test_resolve_cache_wins():
    r = TickerResolver(MAPPING).resolve("Whatever", "IT", ibkr_ticker="XYZ", ibkr_exchange="BVME")
    assert r == ResolvedTicker("XYZ", "BVME", None, "EUR", "cache")


def test_resolve_manual_mapping_normalised():
    # "COMMERZBANK Aktiengesellschaft" must hit the "Commerzbank" mapping entry.
    r = TickerResolver(MAPPING).resolve("COMMERZBANK Aktiengesellschaft", "DE")
    assert r is not None
    assert r.symbol == "CBK"
    assert r.exchange == "IBIS"
    assert r.source == "manual"


def test_resolve_isin_for_de_deal():
    r = TickerResolver({}).resolve("CECONOMY AG", "DE", regulator_ref="BAFIN-DE0007257503-20250901")
    assert r is not None
    assert r.by_isin
    assert r.isin == "DE0007257503"
    assert r.exchange == "IBIS"
    assert r.source == "isin"


def test_resolve_isin_from_ticker_target_fallback():
    r = TickerResolver({}).resolve(
        "Some DE Co", "DE", regulator_ref="garbage", ticker_target="DE000CBK1001"
    )
    assert r is not None and r.isin == "DE000CBK1001"


def test_resolve_unresolved_returns_none():
    # FR deal, no mapping, AMF ref (not an ISIN) → None.
    assert TickerResolver({}).resolve("ORAPI", "FR", regulator_ref="223C1767") is None


def test_manual_beats_isin_when_both_available():
    r = TickerResolver(MAPPING).resolve(
        "Commerzbank", "DE", regulator_ref="BAFIN-DE000CBK1001-20260505"
    )
    assert r is not None and r.source == "manual" and r.symbol == "CBK"


# ------------------------------------------------------------ shipped file
def test_shipped_mapping_file_loads_and_is_valid():
    resolver = TickerResolver.from_file(DEFAULT_MAPPING_PATH)
    # The brief seed entries must resolve.
    r = resolver.resolve("Commerzbank", "DE")
    assert r is not None and r.source == "manual" and r.symbol == "CBK"
