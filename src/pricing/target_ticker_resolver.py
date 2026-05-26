"""Target-side ISIN → Yahoo ticker resolver (Phase 9.1c, V1 minimaliste).

Mirrors :mod:`acquirer_registry` but for the *target* of a deal — needed at
P9.1c-[E] to fetch the target close at announcement-1 business day (audit /
spread context) and extended at [F] for the small-cap validation. Strict key
lookup on the ISIN (which BaFin publishes in ``regulator_ref``); no fuzzy
matching needed since ISINs are unambiguous.

Migration to a SQL table follows the same trigger as acquirer_registry
(Phase 9.2, when the catalog grows past ~10 entries).
"""

from __future__ import annotations

from typing import Final

_ISIN_LENGTH: Final[int] = 12
_ISIN_COUNTRY_PREFIX_LEN: Final[int] = 2

# DE corpus, V1: extend on demand. Order = audit-relevant first (mixed deals),
# then the 12 small-caps the validation step will touch.
TARGET_TICKER_REGISTRY: dict[str, str] = {
    # Mixed offers (P9.1c-[E]):
    "DE000CBK1001": "CBK.DE",  # Commerzbank
    "DE000PSM7770": "PSM.DE",  # ProSiebenSat.1
}


def resolve_target_ticker(isin: str | None) -> str | None:
    """Return the Yahoo ticker for ``isin``, or ``None`` if unknown."""
    if not isin:
        return None
    return TARGET_TICKER_REGISTRY.get(isin)


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
