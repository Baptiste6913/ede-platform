"""P9.2 02d — unit tests for the Consob flag promotion logic.

Tests target the pure `categorize()` function (no DB, no IO) which
implements the first-match categorization rule:

  1. OUTLIER        → failed_validation (non-NULL price outside [0.01, 10 000])
  2. MIXED          → suspect_mixed     (deal_type = 'opas')
  3. MANUAL_REVIEW  → manual_review     (price is None OR target_name partial)
  4. PROMOTABLE     → verified_cash     (else)

The first-match ordering is load-bearing:
- OUTLIER must precede MIXED so Banco BPM (opas + 3.8 B EUR
  controvalore mis-parsed) lands in failed_validation rather than
  propagating the broken value into 02e.
- The non-NULL guard on OUTLIER must come first to avoid
  `TypeError: '<' not supported between instances of 'NoneType'
  and 'Decimal'` on NULL-priced OPAS deals.
- `test_null_price_handled_no_typeerror` defends explicitly.
"""

from __future__ import annotations

from decimal import Decimal

from scripts.promote_consob_flags_02d import DealView, categorize


def _view(
    *,
    deal_type: str = "opa_volontaire_totalitaria",
    offer_price: Decimal | None = Decimal("10.00"),
    target_name: str = "Some Company SpA",
) -> DealView:
    return DealView(
        deal_type=deal_type,
        offer_price=offer_price,
        target_name=target_name,
    )


def test_promotable_cash_in_bounds() -> None:
    flag, outlier = categorize(_view(offer_price=Decimal("8.50")))
    assert flag == "verified_cash"
    assert outlier is False


def test_health_italia_high_price_promoted_with_outlier_flag() -> None:
    # Real corpus case: id 334 Health Italia, offer_price 300 EUR, opa_obligatoire.
    # p95 x 3 = 107.19; 300 > 107.19 => statistical_outlier=True. Still PROMOTABLE.
    flag, outlier = categorize(
        _view(
            deal_type="opa_obligatoire",
            offer_price=Decimal("300.00"),
            target_name="Health Italia Spa",
        )
    )
    assert flag == "verified_cash"
    assert outlier is True


def test_null_price_handled_no_typeerror() -> None:
    # CRITICAL: protects the ordering invariant. If a future refactor
    # moves the numeric bounds check above the None guard, this test will
    # explode with `TypeError: '<' not supported between instances of
    # 'NoneType' and 'Decimal'` instead of returning manual_review.
    flag, outlier = categorize(_view(offer_price=None, target_name="Piovan Spa"))
    assert flag == "manual_review"
    assert outlier is False


def test_pending_parse_to_manual_review() -> None:
    # Even with a valid in-bounds price, the [pending parse] marker on
    # target_name signals that the ingestion was partial and the price
    # extraction integrity on the same PDF is not guaranteed.
    flag, outlier = categorize(_view(offer_price=Decimal("0.68"), target_name="[pending parse]"))
    assert flag == "manual_review"
    assert outlier is False


def test_banco_bpm_outlier_on_cash_type() -> None:
    # Isolates the OUTLIER bounds path on a cash-typed deal. The
    # opas variant of the same scenario (real Banco BPM) is covered
    # by test_banco_bpm_opas_outlier_to_failed_not_mixed below.
    flag, outlier = categorize(
        _view(
            deal_type="opa_volontaire_totalitaria",
            offer_price=Decimal("3828060000"),
        )
    )
    assert flag == "failed_validation"
    assert outlier is False


def test_below_lower_bound_rejected() -> None:
    # Edge guard at the lower bound: 0.005 < 0.01 lower bound.
    flag, outlier = categorize(_view(offer_price=Decimal("0.005")))
    assert flag == "failed_validation"
    assert outlier is False


def test_opas_routed_to_mixed() -> None:
    flag, outlier = categorize(_view(deal_type="opas", offer_price=Decimal("1.80")))
    assert flag == "suspect_mixed"
    assert outlier is False


def test_opas_in_bounds_routes_to_mixed_not_promoted() -> None:
    # OPAS routes to suspect_mixed even when the price is well within
    # the cash bounds envelope (Banca Sistema-class 1.80 EUR). 02e
    # will split cash + share legs; 02d must NOT promote opas to
    # verified_cash on the basis of an in-bounds price alone.
    flag, outlier = categorize(_view(deal_type="opas", offer_price=Decimal("5.00")))
    assert flag == "suspect_mixed"
    assert outlier is False


def test_opas_with_null_price_to_mixed_not_manual_review() -> None:
    # The 2 OPS-prefixed-but-opas-typed deals (Mediobanca, Banca Pop Sondrio)
    # have NULL price. MIXED rule fires first, so they route to suspect_mixed
    # for 02e to resolve — NOT manual_review.
    flag, outlier = categorize(_view(deal_type="opas", offer_price=None))
    assert flag == "suspect_mixed"
    assert outlier is False


def test_banco_bpm_opas_outlier_to_failed_not_mixed() -> None:
    # Banco BPM real case (id 1034): deal_type=opas + 3.828 B EUR
    # (parser captured the controvalore complessivo as unit price).
    # OUTLIER runs before MIXED, so the deal lands in failed_validation
    # — NOT suspect_mixed — to prevent the broken value from
    # propagating into 02e's cash+share split. Defends the rule
    # ordering against regression.
    flag, outlier = categorize(_view(deal_type="opas", offer_price=Decimal("3828060000")))
    assert flag == "failed_validation"
    assert outlier is False


def test_outlier_threshold_exact_boundary() -> None:
    # 107.19 EUR is the THRESHOLD; the rule is strict `>` so equal is NOT
    # an outlier. Health Italia 300 EUR clears it. Guard fence-post regressions.
    flag, outlier = categorize(_view(offer_price=Decimal("107.19")))
    assert flag == "verified_cash"
    assert outlier is False

    flag, outlier = categorize(_view(offer_price=Decimal("107.20")))
    assert flag == "verified_cash"
    assert outlier is True
