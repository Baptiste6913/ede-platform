"""Pure helpers for the P9.1c offer-total recalc (Phase 9.1c).

Kept separate from the orchestration script so the maths can be unit-tested
without spinning up a DB or yfinance: just the calendar walk and the
``cash + share_ratio x acquirer_close`` formula.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

_SATURDAY = 5  # Python weekday(): Mon=0 .. Sun=6


def prev_business_day(d: date) -> date:
    """``d`` minus 1 calendar day, walking back further over Sat/Sun.

    Public holidays are intentionally NOT modelled — they are absorbed by the
    yfinance fetcher's ``max_lookback_days`` fallback (see
    :func:`src.pricing.yfinance_fetcher.get_close_eur`).
    """
    d -= timedelta(days=1)
    while d.weekday() >= _SATURDAY:
        d -= timedelta(days=1)
    return d


def compute_total_eur(
    cash_eur: Decimal | None,
    share_ratio: Decimal,
    acquirer_close_eur: Decimal,
) -> Decimal:
    """Economic value of a mixed offer: ``(cash or 0) + share_ratio x acquirer_close``.

    Quantised to 4 decimals to match ``deals.offer_price_total_eur``
    NUMERIC(12, 4).
    """
    cash = cash_eur if cash_eur is not None else Decimal("0")
    total = cash + share_ratio * acquirer_close_eur
    return total.quantize(Decimal("0.0001"))
