"""Ticker resolver (Phase 8) — deal → IBKR contract spec.

Maps an EDE deal to the inputs IBKR needs to qualify a contract, using a
priority chain (cheapest/most-reliable first):

1. **cache** — `deals.ibkr_ticker` + `deals.ibkr_exchange` already resolved.
2. **manual** — `ticker_mapping.json`, keyed by normalised target name
   (the only reliable path for FR/IT, which carry no ISIN).
3. **isin** — extracted from `regulator_ref` (DE/BaFin: `BAFIN-<ISIN>-<date>`)
   or from `ticker_target` when it is an ISIN; IBKR qualifies by `secIdType=ISIN`.
4. **None** — unresolved; logged for manual review (Sanofi/SAN was a Step-0 case).

This module is pure (no IBKR, no DB) so it is fully unit-testable. The caller
(`IbkrClient.qualify_contract` / executor) turns a `ResolvedTicker` into a live
contract.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import structlog

log = structlog.get_logger()

DEFAULT_MAPPING_PATH = Path(__file__).with_name("ticker_mapping.json")

# Default IBKR primary exchange per jurisdiction (Step-0 verified codes).
JURISDICTION_EXCHANGE = {"FR": "SBF", "IT": "BVME", "DE": "IBIS"}

# ISIN = 2-letter country + 9 alphanumerics + 1 check digit.
ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b")

# Legal-form suffixes stripped before matching a name against the mapping.
_LEGAL_SUFFIXES = (
    "AKTIENGESELLSCHAFT",
    "SPA",
    "S P A",
    "SE",
    "AG",
    "SA",
    "S A",
    "NV",
    "N V",
    "PLC",
    "ASA",
    "AB",
    "OYJ",
    "BV",
    "B V",
    "SAS",
    "SCA",
    "SIIQ",
    "SIM",
)


def normalize_name(name: str) -> str:
    """Uppercase, drop punctuation + legal-form suffixes, collapse spaces.

    "COMMERZBANK Aktiengesellschaft" → "COMMERZBANK";
    "Digital Value Spa" → "DIGITAL VALUE".
    """
    s = re.sub(r"[^A-Za-z0-9 ]", " ", name).upper()
    s = re.sub(r"\s+", " ", s).strip()
    # Strip trailing legal suffixes repeatedly (e.g. "... HOLDING SE" keeps HOLDING).
    changed = True
    while changed:
        changed = False
        for suf in _LEGAL_SUFFIXES:
            if s.endswith(" " + suf):
                s = s[: -(len(suf) + 1)].strip()
                changed = True
    return s


@dataclass(frozen=True, slots=True)
class ResolvedTicker:
    """How to qualify a deal at IBKR. Either (symbol, exchange) or isin is set."""

    symbol: str | None
    exchange: str | None
    isin: str | None
    currency: str
    source: str  # "cache" | "manual" | "isin"

    @property
    def by_isin(self) -> bool:
        return self.isin is not None and self.symbol is None


def extract_isin(*candidates: str | None) -> str | None:
    """Return the first ISIN found in any candidate string, else None."""
    for c in candidates:
        if not c:
            continue
        m = ISIN_RE.search(c)
        if m:
            return m.group(1)
    return None


class TickerResolver:
    """Resolve deals to IBKR contract specs via cache → manual → ISIN."""

    def __init__(self, mapping: dict[str, dict[str, str]] | None = None) -> None:
        # Index the manual mapping by normalised name for robust matching.
        raw = mapping or {}
        self._index: dict[str, dict[str, str]] = {
            normalize_name(name): entry for name, entry in raw.items()
        }

    @classmethod
    def from_file(cls, path: Path | str = DEFAULT_MAPPING_PATH) -> TickerResolver:
        p = Path(path)
        if not p.exists():
            log.warning("ticker_mapping_missing", path=str(p))
            return cls({})
        with p.open(encoding="utf-8") as fh:
            return cls(json.load(fh))

    def resolve(
        self,
        target_name: str,
        juridiction: str,
        regulator_ref: str | None = None,
        ticker_target: str | None = None,
        ibkr_ticker: str | None = None,
        ibkr_exchange: str | None = None,
    ) -> ResolvedTicker | None:
        # 1. cache
        if ibkr_ticker and ibkr_exchange:
            return ResolvedTicker(ibkr_ticker, ibkr_exchange, None, "EUR", "cache")

        # 2. manual mapping
        entry = self._index.get(normalize_name(target_name))
        if entry:
            return ResolvedTicker(
                symbol=entry["symbol"],
                exchange=entry.get("exchange", JURISDICTION_EXCHANGE.get(juridiction, "SMART")),
                isin=None,
                currency=entry.get("currency", "EUR"),
                source="manual",
            )

        # 3. ISIN (DE deals carry it in regulator_ref / ticker_target)
        isin = extract_isin(regulator_ref, ticker_target)
        if isin:
            return ResolvedTicker(
                symbol=None,
                exchange=JURISDICTION_EXCHANGE.get(juridiction, "SMART"),
                isin=isin,
                currency="EUR",
                source="isin",
            )

        # 4. unresolved
        log.warning(
            "ticker_unresolved",
            target_name=target_name,
            juridiction=juridiction,
            regulator_ref=regulator_ref,
        )
        return None
