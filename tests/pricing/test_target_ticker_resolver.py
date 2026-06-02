"""Tests for src.pricing.target_ticker_resolver."""

from __future__ import annotations

from src.pricing.target_ticker_resolver import (
    REJECTED_TICKER_MAPPINGS,
    TARGET_TICKER_MAP,
    isin_from_regulator_ref,
    resolve_target_ticker,
)

# --- resolve_target_ticker ------------------------------------------------


def test_resolve_returns_curated_mapping_when_present() -> None:
    # Commerzbank is in the curated map.
    assert resolve_target_ticker("DE000CBK1001") == TARGET_TICKER_MAP["DE000CBK1001"]


def test_resolve_returns_none_for_unknown_isin_by_default() -> None:
    # An ISIN not in TARGET_TICKER_MAP and not in REJECTED_TICKER_MAPPINGS:
    # default (strict) behaviour returns None.
    assert resolve_target_ticker("DE000FAKE0001") is None


def test_resolve_returns_none_for_none_input() -> None:
    assert resolve_target_ticker(None) is None


def test_resolve_returns_none_for_rejected_even_with_bare_isin_allowed() -> None:
    # ISINs listed in REJECTED_TICKER_MAPPINGS resolved on yfinance to the
    # WRONG security in a previous run; allow_bare_isin must NOT bypass that
    # guard.
    rejected_isin = next(iter(REJECTED_TICKER_MAPPINGS))
    assert resolve_target_ticker(rejected_isin) is None
    assert resolve_target_ticker(rejected_isin, allow_bare_isin=True) is None


def test_resolve_returns_bare_isin_when_allowed_and_not_curated() -> None:
    # P10 fallback for the ~30 DE labelled deals not yet in the curated map.
    assert resolve_target_ticker("DE000FAKE0001", allow_bare_isin=True) == "DE000FAKE0001"


def test_resolve_prefers_curated_over_bare_when_both_apply() -> None:
    # If an ISIN IS in TARGET_TICKER_MAP, the curated value wins even with
    # allow_bare_isin=True.
    isin = "DE000CBK1001"
    assert resolve_target_ticker(isin, allow_bare_isin=True) == TARGET_TICKER_MAP[isin]


# --- isin_from_regulator_ref ---------------------------------------------


def test_isin_from_ref_extracts_valid_isin() -> None:
    assert isin_from_regulator_ref("BAFIN-DE000CBK1001-20260505") == "DE000CBK1001"


def test_isin_from_ref_returns_none_for_legacy_ref() -> None:
    # Pre-P9.1c legacy BaFin refs use a slug, not the ISIN.
    assert isin_from_regulator_ref("BAFIN-philomaxcap-20241004") is None


def test_isin_from_ref_handles_none_and_empty() -> None:
    assert isin_from_regulator_ref(None) is None
    assert isin_from_regulator_ref("") is None
    assert isin_from_regulator_ref("BAFIN") is None
