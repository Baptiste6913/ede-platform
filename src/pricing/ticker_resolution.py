"""Persist OpenFIGI ticker resolution onto deals (Phase 13).

Phase 11 resolved ISIN → Yahoo ticker but only persisted the *flag* and the
reference price; the ticker itself was discarded. Phase 13 needs it live: a
fresh deal must be resolved once and its ticker stored so the decision-time
price provider (yfinance) and the executor (IBKR) can use it without
re-resolving every cycle.

This module is the thin glue between the OpenFIGI resolver and the ``deals``
row:

- :func:`apply_resolution` — pure: write the resolution onto a deal
  (``trading_ticker_yf`` = Yahoo ticker, ``ibkr_ticker`` / ``ibkr_exchange`` =
  broker symbol + exchange, ``ticker_resolution_flag`` = outcome).
- :func:`resolve_and_persist` — resolve one deal's ISIN via OpenFIGI (cache-first,
  off the event loop) then apply. Idempotent: skip via :func:`needs_resolution`.

The flag vocabulary matches Phase 11 (``home_venue`` / ``home_venue_growth`` /
``venue_fallback`` / ``no_match`` / ``unknown_exch`` / ``not_isin``).
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from src.core.models import Deal
    from src.pricing.openfigi_resolver import YahooTickerResult

log = structlog.get_logger()

# Bloomberg exchCode → IBKR exchange code. Mirrors the resolver's
# COUNTRY_TO_BBG_EXCH / BBG_TO_YAHOO_SUFFIX, but targets IBKR routing codes
# rather than Yahoo suffixes. Unknown venues route via SMART (IBKR resolves).
BBG_TO_IBKR_EXCHANGE: dict[str, str] = {
    "FP": "SBF",  # Euronext Paris (main market)
    "XS": "SBF",  # Euronext Growth Paris
    "XH": "SBF",  # Euronext Access / Growth Paris
    "EO": "SBF",  # Euronext Growth Paris (variant)
    "IM": "BVME",  # Borsa Italiana Milano
    "GR": "IBIS",  # Xetra (composite)
    "GY": "IBIS",  # Xetra (segment)
    "NA": "AEB",  # Euronext Amsterdam
    "BB": "ENEXT.BE",  # Euronext Brussels
    "SM": "BM",  # Bolsa de Madrid
    "LN": "LSE",  # London Stock Exchange
}

# Flags that record a *processing outcome*, not a resolution provenance. A
# backfill must NOT overwrite these with the resolution source: e.g. a
# premium_out_of_bounds deal (corrupt offer — COVIVIO/VOGO/EEM) resolves cleanly
# to home_venue, but keeping the home_venue flag would re-expose it to the
# trading gate. Preserve the outcome; only add the ticker columns.
PROCESSING_OUTCOME_FLAGS: frozenset[str] = frozenset(
    {"premium_out_of_bounds", "no_price_data", "manual_review"}
)

# ISIN = 2-letter country + 9 alphanumerics + 1 check digit.
_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def is_isin(value: str | None) -> bool:
    """True if ``value`` is a well-formed ISIN."""
    return bool(value) and bool(_ISIN_RE.match(value or ""))


def bbg_to_ibkr_exchange(exch_code_bbg: str | None) -> str:
    """IBKR exchange code for a Bloomberg exchCode (SMART for unknown)."""
    if not exch_code_bbg:
        return "SMART"
    return BBG_TO_IBKR_EXCHANGE.get(exch_code_bbg, "SMART")


def ibkr_symbol_from_yahoo(yahoo_ticker: str) -> str:
    """Broker symbol = Yahoo ticker without its venue suffix ('COVH.PA' → 'COVH')."""
    return yahoo_ticker.rsplit(".", 1)[0]


def apply_resolution(deal: Deal, result: YahooTickerResult) -> str:
    """Write an OpenFIGI resolution onto ``deal``; return the persisted flag.

    Sets ``ticker_resolution_flag`` always; the ticker columns only when a
    priceable Yahoo ticker was resolved (NO_MATCH / UNKNOWN_EXCH leave them NULL).
    """
    flag = result.source.value.replace("openfigi_", "") if result.source else "no_match"
    deal.ticker_resolution_flag = flag
    if result.yahoo_ticker:
        deal.trading_ticker_yf = result.yahoo_ticker
        deal.ibkr_ticker = ibkr_symbol_from_yahoo(result.yahoo_ticker)
        deal.ibkr_exchange = bbg_to_ibkr_exchange(result.exch_code_bbg)
    return flag


def needs_resolution(deal: Deal) -> bool:
    """True if the deal has never been through resolution (flag is NULL).

    Re-resolution is not attempted for an already-flagged deal (incl. no_match /
    not_isin) — that is the backfill's job, not the per-cycle hot path.
    """
    return deal.ticker_resolution_flag is None


class _OpenFIGILike(Protocol):
    def resolve_isin_to_yahoo_ticker(self, isin: str) -> YahooTickerResult: ...


async def resolve_and_persist(deal: Deal, openfigi: _OpenFIGILike) -> str:
    """Resolve one deal's ISIN (cache-first, off the loop) and persist it.

    Returns the flag. A deal without an ISIN is flagged ``not_isin`` (no HTTP).
    """
    isin = deal.ticker_target if is_isin(deal.ticker_target) else None
    if isin is None:
        deal.ticker_resolution_flag = "not_isin"
        log.info("ticker_resolution_not_isin", deal_id=deal.id)
        return "not_isin"
    # OpenFIGI client is sync (httpx.Client); keep the cron loop responsive.
    result = await asyncio.to_thread(openfigi.resolve_isin_to_yahoo_ticker, isin)
    flag = apply_resolution(deal, result)
    log.info(
        "ticker_resolved",
        deal_id=deal.id,
        isin=isin,
        flag=flag,
        yahoo_ticker=deal.trading_ticker_yf,
    )
    return flag
