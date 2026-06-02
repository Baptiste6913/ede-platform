"""OpenFIGI ISIN → Yahoo-ticker resolver (Phase 11).

Phase 10 demonstrated that yfinance bare-ISIN lookup is unsafe: ~25% real
success and *wrong-security* false positives (a Turkey ETF for a delisted AG,
penny stocks for the wrong issuer) that would silently poison an ML backfill.

OpenFIGI (Bloomberg's free, no-KYC mapping service) resolves an ISIN to the
*correct issuer* every time it is listed — the pre-flight (artifacts/phase-11/
openfigi_preflight.md) confirmed 3/3 on Mediobanca / Sanofi / SAP. The catch is
that a single ISIN returns dozens-to-hundreds of venue rows (one per Bloomberg
exchange), all sharing the same ``compositeFIGI`` / ``shareClassFIGI``. So the
problem is no longer "is this the right company?" (it always is) but "which
listing venue do we price against?". This module:

1. ``resolve_isin``     — POST /v3/mapping (no exchCode hint), keep equity rows.
2. ``select_home_venue``— pick the home-market row via ISIN-country → Bloomberg
   exchCode, else fall back to the dominant ``compositeFIGI`` (flagged).
3. ``bbg_to_yahoo_suffix`` — map the Bloomberg exchCode to a Yahoo suffix.
4. ``resolve_isin_to_yahoo_ticker`` — orchestrate the three into a final
   ``TICKER.SUFFIX`` plus a confidence flag.

NB on exchCode: OpenFIGI uses **Bloomberg** 2-letter codes (FP/IM/GR/GY), *not*
MIC codes (XPAR/MTAA fail with "No identifier found"). See the pre-flight memo.

Resolving the right issuer is necessary but not sufficient: the Step-2
checkpoint still cross-checks the resolved ticker's close vs the offer price
(the Phase-10 deviation guard) before any backfill, to catch suffix-mapping
errors and stale/delisted venues.

Module-level config (``API_URL``, ``RATE_LIMIT_PER_MIN``, ``CACHE_PATH``,
``CACHE_TTL``, ``REQUEST_TIMEOUT``, ``RETRY_BACKOFFS``) are plain attributes (not
``Final``) so tests can monkeypatch them.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

log = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

API_URL: str = "https://api.openfigi.com/v3/mapping"
# Free tier with key: 25 req/min. 1.0/rate → 2.4 s min interval between calls.
RATE_LIMIT_PER_MIN: int = 25
# OpenFIGI accepts up to 100 jobs per /v3/mapping request (with key).
MAX_JOBS_PER_REQUEST: int = 100
CACHE_PATH: Path = _REPO_ROOT / "artifacts" / "phase-11" / "openfigi_cache.json"
CACHE_TTL: timedelta = timedelta(days=30)
REQUEST_TIMEOUT: float = 30.0
RETRY_BACKOFFS: tuple[float, ...] = (1.0, 3.0, 9.0)

HTTP_TOO_MANY_REQUESTS: int = 429
_RETRYABLE_STATUS: frozenset[int] = frozenset({HTTP_TOO_MANY_REQUESTS, 500, 502, 503, 504})

# securityType values we accept as the priceable equity line of an issuer.
# Deliberately narrow: Depositary Receipts / ADRs share the issuer but trade a
# different instrument, so they are excluded to avoid mispricing. Extend on
# demand as the 187-deal corpus surfaces new types.
EQUITY_SECURITY_TYPES: frozenset[str] = frozenset({"Common Stock", "REIT"})

# ISIN country prefix → Bloomberg exchCode(s) of the home listing, priority
# order first. DE lists on both GR (composite/Xetra) and GY (Xetra segment);
# GR is preferred. Extensible — add jurisdictions as the corpus grows.
COUNTRY_TO_BBG_EXCH: dict[str, tuple[str, ...]] = {
    "FR": ("FP",),  # Euronext Paris
    "IT": ("IM",),  # Borsa Italiana Milano
    "DE": ("GR", "GY"),  # Xetra composite, then Xetra segment
    "NL": ("NA",),  # Euronext Amsterdam
    "BE": ("BB",),  # Euronext Brussels
    "ES": ("SM",),  # Bolsa de Madrid
    "GB": ("LN",),  # London Stock Exchange
}

# Bloomberg exchCode → Yahoo Finance suffix. Unknown codes return None and the
# orchestrator emits ``OPENFIGI_UNKNOWN_EXCH`` rather than guessing a suffix.
BBG_TO_YAHOO_SUFFIX: dict[str, str] = {
    "FP": ".PA",  # Euronext Paris
    "IM": ".MI",  # Borsa Italiana Milano
    "GR": ".DE",  # Xetra (composite)
    "GY": ".DE",  # Xetra (segment) — same Yahoo suffix as GR
    "NA": ".AS",  # Euronext Amsterdam
    "BB": ".BR",  # Euronext Brussels
    "SM": ".MC",  # Bolsa de Madrid
    "LN": ".L",  # London Stock Exchange
}

_ISIN_LENGTH: int = 12


class OpenFIGISource(StrEnum):
    """Provenance / confidence label for a resolved ticker."""

    HOME_VENUE = "openfigi_home_venue"  # matched the expected home exchCode
    VENUE_FALLBACK = "openfigi_venue_fallback"  # right issuer, secondary venue
    NO_MATCH = "openfigi_no_match"  # no equity row for this ISIN
    UNKNOWN_EXCH = "openfigi_unknown_exch"  # exchCode absent from suffix table


@dataclass(frozen=True)
class OpenFIGIRow:
    """One venue row from a /v3/mapping match (equity rows only)."""

    ticker: str
    exch_code: str
    security_type: str
    market_sector: str
    composite_figi: str
    share_class_figi: str
    name: str


@dataclass(frozen=True)
class OpenFIGIResult:
    """Equity rows OpenFIGI returned for an ISIN (empty tuple = no match)."""

    isin: str
    rows: tuple[OpenFIGIRow, ...]


@dataclass(frozen=True)
class YahooTickerResult:
    """Final resolution outcome for an ISIN.

    ``yahoo_ticker`` is ``None`` for ``NO_MATCH`` and ``UNKNOWN_EXCH``; callers
    must route those to manual_review (never pass a guessed ticker downstream).
    """

    isin: str
    yahoo_ticker: str | None
    exch_code_bbg: str | None
    figi: str | None
    source: OpenFIGISource


def bbg_to_yahoo_suffix(exch_code_bbg: str) -> str | None:
    """Return the Yahoo suffix for a Bloomberg exchCode, or ``None`` if unknown.

    ``None`` is a *defensive* signal — the caller flags ``UNKNOWN_EXCH`` and
    routes to manual_review instead of fabricating a suffix.
    """
    return BBG_TO_YAHOO_SUFFIX.get(exch_code_bbg)


def select_home_venue(
    rows: Sequence[OpenFIGIRow], isin: str
) -> tuple[str, str, str, OpenFIGISource] | None:
    """Pick the venue to price against from an ISIN's equity rows.

    Returns ``(ticker, exch_code_bbg, composite_figi, source)`` where ``source``
    is :attr:`OpenFIGISource.HOME_VENUE` when a row matched the expected home
    exchCode, or :attr:`OpenFIGISource.VENUE_FALLBACK` when no home row existed
    and we fell back to the dominant ``compositeFIGI`` (still the right issuer,
    just a secondary listing). Returns ``None`` when there are no equity rows.
    """
    if not rows:
        return None

    country = isin[:2].upper()
    for exch in COUNTRY_TO_BBG_EXCH.get(country, ()):
        for row in rows:
            if row.exch_code == exch:
                return (row.ticker, row.exch_code, row.composite_figi, OpenFIGISource.HOME_VENUE)

    # No home-venue row: fall back to the most common compositeFIGI (the issuer
    # with the most listings — robust against a stray secondary security), then
    # the first equity row carrying it.
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.composite_figi] = counts.get(row.composite_figi, 0) + 1
    dominant = max(counts, key=lambda figi: counts[figi])
    fallback = next(row for row in rows if row.composite_figi == dominant)
    log.info(
        "openfigi.venue_fallback",
        isin=isin,
        country=country,
        chosen_exch=fallback.exch_code,
        composite_figi=dominant,
    )
    return (
        fallback.ticker,
        fallback.exch_code,
        fallback.composite_figi,
        OpenFIGISource.VENUE_FALLBACK,
    )


class OpenFIGIResolver:
    """Thin, rate-limited client over the OpenFIGI /v3/mapping endpoint.

    Construct once and reuse: the instance holds the HTTP session, the disk
    cache, and the throttle clock. ``api_key`` is required (the free tier still
    works without one but at 25 req/min vs 5, and we always pass it).
    """

    def __init__(
        self,
        api_key: str,
        *,
        session: httpx.Client | None = None,
        cache_path: Path | None = None,
        use_cache: bool = True,
        rate_per_min: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._session = session if session is not None else httpx.Client()
        self._cache_path = cache_path if cache_path is not None else CACHE_PATH
        self._use_cache = use_cache
        rate = rate_per_min if rate_per_min is not None else RATE_LIMIT_PER_MIN
        self._min_interval = 60.0 / rate
        self._last_call: float = 0.0
        self._cache: dict[str, dict[str, Any]] | None = None

    # ----------------------------------------------------------------- HTTP

    def _throttle(self) -> None:
        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _post(self, jobs: list[dict[str, str]]) -> list[dict[str, Any]]:
        """POST a batch of mapping jobs; retry on 429/5xx with backoff.

        Returns the raw per-job response array. Raises on non-retryable HTTP
        errors and on retry exhaustion (the caller decides how to degrade).
        """
        headers = {"Content-Type": "application/json", "X-OPENFIGI-APIKEY": self._api_key}
        attempts = 1 + len(RETRY_BACKOFFS)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            if attempt > 0:
                time.sleep(RETRY_BACKOFFS[attempt - 1])
            self._throttle()
            try:
                resp = self._session.post(
                    API_URL, headers=headers, json=jobs, timeout=REQUEST_TIMEOUT
                )
                if resp.status_code in _RETRYABLE_STATUS:
                    log.warning(
                        "openfigi.retryable_status", status=resp.status_code, attempt=attempt
                    )
                    last_exc = httpx.HTTPError(f"status {resp.status_code}")
                    continue
                resp.raise_for_status()
                body = resp.json()
                if not isinstance(body, list):
                    raise ValueError(f"unexpected OpenFIGI response shape: {type(body).__name__}")
                return body
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                log.debug("openfigi.post_attempt_failed", attempt=attempt, error=str(exc))
        raise RuntimeError(f"OpenFIGI POST failed after {attempts} attempts: {last_exc}")

    # ------------------------------------------------------------- parsing

    @staticmethod
    def _equity_rows(data: Iterable[dict[str, Any]]) -> tuple[OpenFIGIRow, ...]:
        rows: list[OpenFIGIRow] = []
        for d in data:
            if d.get("securityType") not in EQUITY_SECURITY_TYPES:
                continue
            if d.get("marketSector") != "Equity":
                continue
            ticker = d.get("ticker")
            exch = d.get("exchCode")
            if not ticker or not exch:
                continue
            rows.append(
                OpenFIGIRow(
                    ticker=str(ticker),
                    exch_code=str(exch),
                    security_type=str(d.get("securityType", "")),
                    market_sector=str(d.get("marketSector", "")),
                    composite_figi=str(d.get("compositeFIGI", "")),
                    share_class_figi=str(d.get("shareClassFIGI", "")),
                    name=str(d.get("name", "")),
                )
            )
        return tuple(rows)

    # ------------------------------------------------------------- resolve

    def resolve_isin(self, isin: str) -> OpenFIGIResult:
        """Map ``isin`` to its equity venue rows (no exchCode hint).

        Misses (``"No identifier found"`` warning or empty data) yield an empty
        ``rows`` tuple, never an exception.
        """
        body = self._post([{"idType": "ID_ISIN", "idValue": isin}])
        first = body[0] if body else {}
        if "data" not in first:
            # warning ("No identifier found") or error — treated as a clean miss.
            return OpenFIGIResult(isin=isin, rows=())
        return OpenFIGIResult(isin=isin, rows=self._equity_rows(first["data"]))

    def resolve_isin_to_yahoo_ticker(self, isin: str) -> YahooTickerResult:
        """End-to-end: ISIN → ``TICKER.SUFFIX`` + confidence flag (cached)."""
        cached = self._cache_get(isin)
        if cached is not None:
            return cached
        result = self._resolve_uncached(isin)
        self._cache_put(result)
        return result

    def _resolve_uncached(self, isin: str) -> YahooTickerResult:
        rows = self.resolve_isin(isin).rows
        selection = select_home_venue(rows, isin)
        if selection is None:
            log.info("openfigi.no_match", isin=isin)
            return YahooTickerResult(isin, None, None, None, OpenFIGISource.NO_MATCH)
        ticker, exch, figi, source = selection
        suffix = bbg_to_yahoo_suffix(exch)
        if suffix is None:
            log.warning("openfigi.unknown_exch", isin=isin, exch_code=exch)
            return YahooTickerResult(isin, None, exch, figi, OpenFIGISource.UNKNOWN_EXCH)
        return YahooTickerResult(isin, f"{ticker}{suffix}", exch, figi, source)

    def resolve_batch(self, isins: Sequence[str]) -> dict[str, YahooTickerResult]:
        """Resolve many ISINs, batching up to 100 jobs per HTTP request.

        Cached ISINs are served from disk; the rest are chunked into
        ``MAX_JOBS_PER_REQUEST`` POSTs. Order within a chunk maps 1:1 to the
        response array (OpenFIGI guarantees positional correspondence).
        """
        out: dict[str, YahooTickerResult] = {}
        pending: list[str] = []
        for isin in isins:
            cached = self._cache_get(isin)
            if cached is not None:
                out[isin] = cached
            elif isin not in out:
                pending.append(isin)

        for start in range(0, len(pending), MAX_JOBS_PER_REQUEST):
            chunk = pending[start : start + MAX_JOBS_PER_REQUEST]
            jobs = [{"idType": "ID_ISIN", "idValue": isin} for isin in chunk]
            body = self._post(jobs)
            for isin, entry in zip(chunk, body, strict=True):
                rows = (
                    self._equity_rows(entry["data"])
                    if isinstance(entry, dict) and "data" in entry
                    else ()
                )
                result = self._from_rows(isin, rows)
                self._cache_put(result)
                out[isin] = result
        return out

    @staticmethod
    def _from_rows(isin: str, rows: tuple[OpenFIGIRow, ...]) -> YahooTickerResult:
        selection = select_home_venue(rows, isin)
        if selection is None:
            return YahooTickerResult(isin, None, None, None, OpenFIGISource.NO_MATCH)
        ticker, exch, figi, source = selection
        suffix = bbg_to_yahoo_suffix(exch)
        if suffix is None:
            return YahooTickerResult(isin, None, exch, figi, OpenFIGISource.UNKNOWN_EXCH)
        return YahooTickerResult(isin, f"{ticker}{suffix}", exch, figi, source)

    # --------------------------------------------------------------- cache

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        if self._use_cache and self._cache_path.exists():
            try:
                loaded = json.loads(self._cache_path.read_text(encoding="utf-8"))
                self._cache = loaded if isinstance(loaded, dict) else {}
            except (json.JSONDecodeError, OSError):
                self._cache = {}
        else:
            self._cache = {}
        return self._cache

    def _cache_get(self, isin: str) -> YahooTickerResult | None:
        if not self._use_cache:
            return None
        entry = self._load_cache().get(isin)
        if entry is None:
            return None
        resolved_at = datetime.fromisoformat(entry["resolved_at"])
        if datetime.now(tz=UTC) - resolved_at > CACHE_TTL:
            return None
        return YahooTickerResult(
            isin=isin,
            yahoo_ticker=entry["yahoo_ticker"],
            exch_code_bbg=entry["exch_code_bbg"],
            figi=entry["figi"],
            source=OpenFIGISource(entry["source"]),
        )

    def _cache_put(self, result: YahooTickerResult) -> None:
        if not self._use_cache:
            return
        cache = self._load_cache()
        cache[result.isin] = {
            "yahoo_ticker": result.yahoo_ticker,
            "exch_code_bbg": result.exch_code_bbg,
            "figi": result.figi,
            "source": str(result.source),
            "resolved_at": datetime.now(tz=UTC).isoformat(),
        }
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
