"""Acquirer lookup (Phase 9.1c, V1 minimaliste).

Maps PDF-extracted acquirer names to the canonical ISIN / yfinance ticker / EU
share-class metadata. Two entries cover the two known suspect_mixed BaFin
deals (UniCredit→Commerzbank, MFE→ProSieben). When the corpus grows past
~10 acquirers (Phase 9.2 ISIN extraction) this becomes a SQL table; for V1 a
Python dict is enough and avoids another migration.

The resolution is deliberately **fuzzy** (substring match on a normalised
lowercase form): BaFin PDFs spell the same acquirer multiple ways
("UniCredit S.p.A.", "MFE-MEDIAFOREUROPE N.V.") and a strict key lookup is
brittle. The hit count is tiny so the false-positive risk is bounded.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AcquirerInfo:
    """Canonical metadata for a single acquirer security."""

    isin: str
    ticker_yf: str
    name: str
    currency_native: str  # informational; the fetcher does the FX conversion


# Keys are the resolver's canonical anchors (lowercase, space-normalised);
# resolve_acquirer uses substring match against them, not exact-key lookup.
ACQUIRER_REGISTRY: dict[str, AcquirerInfo] = {
    "unicredit": AcquirerInfo(
        isin="IT0005239360",
        ticker_yf="UCG.MI",
        name="UniCredit S.p.A.",
        currency_native="EUR",
    ),
    "mfe mediaforeurope": AcquirerInfo(
        isin="NL0015001OI1",
        ticker_yf="MFEA.MI",  # class A; class B is MFEB.MI
        name="MFE-MediaForEurope N.V.",
        currency_native="EUR",
    ),
}


def resolve_acquirer(raw_name: str) -> AcquirerInfo | None:
    """Resolve an acquirer name as written in a BaFin PDF.

    Normalises whitespace + case, then substring-matches against the known
    anchors. Returns ``None`` when no anchor hits — caller decides whether
    that's a raise (V1: only 2 known acquirers, miss == real bug) or a skip.
    """
    normalised = " ".join(raw_name.lower().split())
    if "unicredit" in normalised:
        return ACQUIRER_REGISTRY["unicredit"]
    if "mfe" in normalised or "mediaforeurope" in normalised:
        return ACQUIRER_REGISTRY["mfe mediaforeurope"]
    return None
