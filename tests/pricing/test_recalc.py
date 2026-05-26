"""Tests for the pure recalc helpers (Phase 9.1c)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.pricing.recalc import compute_total_eur, prev_business_day
from src.pricing.target_ticker_resolver import isin_from_regulator_ref, resolve_target_ticker

# -------------------------------------------------------------- business day


def test_prev_business_day_tuesday_to_monday():
    # Commerzbank: announcement Tue 2026-05-05 -> Mon 2026-05-04.
    assert prev_business_day(date(2026, 5, 5)) == date(2026, 5, 4)


def test_prev_business_day_thursday_to_wednesday():
    # ProSieben: announcement Thu 2025-05-08 -> Wed 2025-05-07.
    assert prev_business_day(date(2025, 5, 8)) == date(2025, 5, 7)


def test_prev_business_day_monday_skips_weekend():
    # Mon 2026-05-04 -> previous Friday 2026-05-01.
    assert prev_business_day(date(2026, 5, 4)) == date(2026, 5, 1)


def test_prev_business_day_sunday_skipped():
    # Sun 2026-05-03 -> Fri 2026-05-01 (Sun -> Sat -> Fri).
    assert prev_business_day(date(2026, 5, 3)) == date(2026, 5, 1)


# ----------------------------------------------------------------- formula


def test_compute_total_share_only_swap():
    # Commerzbank-like: no cash leg; 0.485 x 64.06 = 31.0691.
    total = compute_total_eur(None, Decimal("0.485"), Decimal("64.06"))
    assert total == Decimal("31.0691")


def test_compute_total_cash_plus_share():
    # ProSieben-like: 4.48 + 0.4 x 2.922 = 4.48 + 1.1688 = 5.6488.
    total = compute_total_eur(Decimal("4.48"), Decimal("0.4"), Decimal("2.922"))
    assert total == Decimal("5.6488")


def test_compute_total_zero_cash_is_same_as_none():
    # Explicit zero cash is equivalent to a missing cash leg (share-only swap).
    assert compute_total_eur(Decimal("0"), Decimal("0.5"), Decimal("100")) == compute_total_eur(
        None, Decimal("0.5"), Decimal("100")
    )


def test_compute_total_quantised_to_four_decimals():
    # Decimal("0.123456789") x Decimal("10") = Decimal("1.23456789") -> quantised 1.2346.
    total = compute_total_eur(None, Decimal("0.123456789"), Decimal("10"))
    assert total == Decimal("1.2346")


# ----------------------------------------------------------------- resolvers


def test_resolve_target_ticker_known_isin():
    assert resolve_target_ticker("DE000CBK1001") == "CBK.DE"
    assert resolve_target_ticker("DE000PSM7770") == "PSM.DE"


def test_resolve_target_ticker_unknown_returns_none():
    assert resolve_target_ticker("DE0000000000") is None
    assert resolve_target_ticker(None) is None


def test_isin_from_regulator_ref_extracts_valid_isin():
    assert isin_from_regulator_ref("BAFIN-DE000CBK1001-20260505") == "DE000CBK1001"
    assert isin_from_regulator_ref("BAFIN-DE000PSM7770-20250508") == "DE000PSM7770"


@pytest.mark.parametrize(
    "ref",
    [None, "", "BAFIN-philomaxcap-20241004", "BAFIN-too-short", "DE000CBK1001"],
)
def test_isin_from_regulator_ref_rejects_non_isin(ref):
    assert isin_from_regulator_ref(ref) is None
