"""Target-side ISIN → Yahoo ticker resolver (Phase 9.1c, V1 minimaliste).

Mirrors :mod:`acquirer_registry` but for the *target* of a deal — needed at
P9.1c-[E] to fetch the target close at announcement-1 business day (audit /
spread context) and extended at [F] for the small-cap validation. Strict key
lookup on the ISIN (which BaFin publishes in ``regulator_ref``); no fuzzy
matching needed since ISINs are unambiguous.

``REJECTED_TICKER_MAPPINGS`` documents tickers that *resolved* on yfinance but
to the *wrong* security — anti-regression memo so a future operator does not
re-attempt them. Migration to a SQL table follows the same trigger as
:mod:`acquirer_registry` (Phase 9.2, when the catalog grows past ~10 entries).
"""

from __future__ import annotations

from typing import Final

_ISIN_LENGTH: Final[int] = 12
_ISIN_COUNTRY_PREFIX_LEN: Final[int] = 2

# DE corpus, V1: extend on demand. Order = audit-relevant first.
TARGET_TICKER_MAP: dict[str, str] = {
    # Mixed offers (P9.1c-[E]):
    "DE000CBK1001": "CBK.DE",  # Commerzbank
    "DE000PSM7770": "PSM.DE",  # ProSiebenSat.1
    # Small-cap validation (P9.1c-[F], probe-confirmed; deviation < 10% vs offer).
    # The other 6 small-caps from the audit miss yfinance entirely (delisted
    # post-OPA) and route to manual_review.
    "DE0006569403": "ALG.DE",  # Albis Leasing (close 2.61 EUR vs offer 2.80, dev 7.1%)
    "DE0007857476": "KA8.DE",  # Klassik Radio (close 3.62 EUR vs offer 3.70, dev 2.1%)
    "DE0007257503": "CEC.DE",  # CECONOMY     (close 4.45 EUR vs offer 4.60, dev 3.4%)
}


# Mappings that LOOKED to resolve on yfinance but to the wrong security. Kept
# out of TARGET_TICKER_MAP so the fetcher does not waste cache / quota on
# them; documented here as an anti-regression memo. Format:
#   ISIN → (ticker_tried, reason)
REJECTED_TICKER_MAPPINGS: dict[str, tuple[str, str]] = {
    "DE0007504508": (
        "TUR.DE",
        "TUR.DE resolves to the iShares MSCI Turkey ETF (~50 EUR), not Turbon AG "
        "(offer 3.34 EUR). Turbon AG appears delisted; route to manual_review.",
    ),
    "DE0005653604": (
        "MEN.F",
        "MEN.F resolves to a penny stock (~0.03 EUR), not MedNation AG "
        "(offer 1.50 EUR). Likely delisted; route to manual_review.",
    ),
}


def resolve_target_ticker(isin: str | None, *, allow_bare_isin: bool = False) -> str | None:
    """Return the Yahoo ticker for ``isin``, or ``None`` if unknown.

    Returns ``None`` for ISINs explicitly listed in ``REJECTED_TICKER_MAPPINGS``
    even though a guess existed — those mappings are known wrong.

    ``allow_bare_isin`` (Phase 10) — when ``True``, ISINs that are neither in
    ``TARGET_TICKER_MAP`` nor in ``REJECTED_TICKER_MAPPINGS`` are returned
    as-is so yfinance can attempt a direct ISIN lookup. Off by default for
    backward compatibility (Phase 9 callers expected strict-map semantics).
    Phase 10 reference-price fetcher uses the bare-ISIN fallback to cover
    the ~30 DE labelled deals not yet in the curated map.
    """
    if not isin:
        return None
    if isin in REJECTED_TICKER_MAPPINGS:
        return None
    mapped = TARGET_TICKER_MAP.get(isin)
    if mapped is not None:
        return mapped
    if allow_bare_isin:
        return isin
    return None


def isin_from_regulator_ref(regulator_ref: str | None) -> str | None:
    """Extract the ISIN from a BaFin ``regulator_ref`` formatted as
    ``"BAFIN-<ISIN>-<YYYYMMDD>"``. Returns ``None`` when the 2nd field is not a
    valid alphanumeric ISIN (e.g. the legacy ``BAFIN-philomaxcap-20241004``).
    """
    if not regulator_ref:
        return None
    parts = regulator_ref.split("-")
    if not parts[1:]:
        return None
    candidate = parts[1]
    if (
        len(candidate) == _ISIN_LENGTH
        and candidate.isalnum()
        and candidate[:_ISIN_COUNTRY_PREFIX_LEN].isalpha()
    ):
        return candidate
    return None
