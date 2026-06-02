"""Unit tests for :mod:`src.pricing.openfigi_resolver`.

No live HTTP: a :class:`FakeSession` is injected and returns pre-built response
payloads modelled on the Phase-10 / Step-0 pre-flight JSON (Mediobanca / Sanofi
/ SAP). ``time.sleep`` is neutralised so throttle + retry backoffs don't slow
the suite. Each cache test uses an isolated file under ``tmp_path``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from src.pricing import openfigi_resolver as r
from src.pricing.openfigi_resolver import (
    OpenFIGIResolver,
    OpenFIGIRow,
    OpenFIGISource,
    bbg_to_yahoo_suffix,
    select_home_venue,
    strip_currency_suffix,
)

# --------------------------------------------------------------- fakes/helpers


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPError(f"status {self.status_code}")


class FakeSession:
    """Returns queued responses in order; records each posted job batch."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def post(
        self, url: str, *, headers: dict[str, str], json: list[dict[str, str]], timeout: float
    ) -> FakeResponse:
        self.calls.append(json)
        return self._responses.pop(0)


def _row(
    ticker: str,
    exch: str,
    *,
    sec: str = "Common Stock",
    sector: str = "Equity",
    composite: str = "COMP1",
    share_class: str = "SC1",
    name: str = "ACME SPA",
) -> dict[str, str]:
    return {
        "ticker": ticker,
        "exchCode": exch,
        "securityType": sec,
        "marketSector": sector,
        "compositeFIGI": composite,
        "shareClassFIGI": share_class,
        "name": name,
    }


def _match(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [{"data": rows}]


def _resolver(
    responses: list[FakeResponse], tmp_path: Any, *, use_cache: bool = False
) -> tuple[OpenFIGIResolver, FakeSession]:
    session = FakeSession(responses)
    res = OpenFIGIResolver(
        "test-key",
        session=session,  # type: ignore[arg-type]
        cache_path=tmp_path / "openfigi_cache.json",
        use_cache=use_cache,
    )
    return res, session


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _s: None)


# Pre-flight-shaped fixtures (subset of venue rows per ISIN).
MEDIOBANCA = _match(
    [
        _row("MB", "IM", composite="BBG000BBKY05"),
        _row("ME9", "GR", composite="BBG000BN54T1"),
        _row("MDIBF", "US", composite="BBG000C1KCS4"),
    ]
)
SANOFI = _match(
    [
        _row("SAN", "FP", composite="BBG000BWBBF3"),
        _row("SNW", "GR", composite="BBG000BWJRH8"),
    ]
)
SAP = _match(
    [
        _row("SAP", "SW", composite="BBG000BDTGP4"),
        _row("SAP", "GR", composite="BBG000BG7DY8"),
        _row("SAP", "GY", composite="BBG000BG7DY8"),
    ]
)


# --------------------------------------------------------------- resolve_isin


def test_resolve_isin_keeps_equity_rows(tmp_path: Any) -> None:
    res, _ = _resolver([FakeResponse(MEDIOBANCA)], tmp_path)
    out = res.resolve_isin("IT0000062957")
    assert out.isin == "IT0000062957"
    assert len(out.rows) == 3
    assert all(isinstance(row, OpenFIGIRow) for row in out.rows)
    assert {row.exch_code for row in out.rows} == {"IM", "GR", "US"}


def test_resolve_isin_no_identifier_found_is_clean_miss(tmp_path: Any) -> None:
    res, _ = _resolver([FakeResponse([{"warning": "No identifier found."}])], tmp_path)
    out = res.resolve_isin("XX0000000000")
    assert out.rows == ()


def test_resolve_isin_filters_non_equity(tmp_path: Any) -> None:
    bonds = _match([_row("ACME", "IM", sec="Corp Bond", sector="Corp")])
    res, _ = _resolver([FakeResponse(bonds)], tmp_path)
    assert res.resolve_isin("IT0000000000").rows == ()


# -------------------------------------------------------------- happy e2e


@pytest.mark.parametrize(
    ("isin", "payload", "expected_ticker", "expected_exch"),
    [
        ("IT0000062957", MEDIOBANCA, "MB.MI", "IM"),
        ("FR0000120578", SANOFI, "SAN.PA", "FP"),
        ("DE0007164600", SAP, "SAP.DE", "GR"),
    ],
)
def test_resolve_to_yahoo_home_venue(
    tmp_path: Any,
    isin: str,
    payload: list[dict[str, Any]],
    expected_ticker: str,
    expected_exch: str,
) -> None:
    res, _ = _resolver([FakeResponse(payload)], tmp_path)
    out = res.resolve_isin_to_yahoo_ticker(isin)
    assert out.yahoo_ticker == expected_ticker
    assert out.exch_code_bbg == expected_exch
    assert out.source is OpenFIGISource.HOME_VENUE


# ----------------------------------------------------------- select_home_venue


def test_select_home_venue_de_prefers_gr_over_gy() -> None:
    rows = [
        OpenFIGIRow("SAP", "GY", "Common Stock", "Equity", "C1", "S1", "SAP SE"),
        OpenFIGIRow("SAP", "GR", "Common Stock", "Equity", "C1", "S1", "SAP SE"),
    ]
    sel = select_home_venue(rows, "DE0007164600")
    assert sel is not None
    assert sel[1] == "GR"
    assert sel[3] is OpenFIGISource.HOME_VENUE


def test_select_home_venue_de_falls_to_gy_when_no_gr() -> None:
    rows = [OpenFIGIRow("SAP", "GY", "Common Stock", "Equity", "C1", "S1", "SAP SE")]
    sel = select_home_venue(rows, "DE0007164600")
    assert sel is not None
    assert sel[1] == "GY"
    assert sel[3] is OpenFIGISource.HOME_VENUE


def test_select_home_venue_empty_rows_returns_none() -> None:
    assert select_home_venue([], "FR0000120578") is None


def test_select_home_venue_fallback_uses_dominant_composite() -> None:
    # FR ISIN but no FP row → fallback to the most-listed compositeFIGI.
    rows = [
        OpenFIGIRow("ACME", "GR", "Common Stock", "Equity", "DOMINANT", "S1", "ACME"),
        OpenFIGIRow("ACME", "US", "Common Stock", "Equity", "DOMINANT", "S1", "ACME"),
        OpenFIGIRow("STRAY", "LN", "Common Stock", "Equity", "OTHER", "S2", "STRAY"),
    ]
    sel = select_home_venue(rows, "FR0000000000")
    assert sel is not None
    ticker, exch, figi, source = sel
    assert exch == "GR"
    assert figi == "DOMINANT"
    assert source is OpenFIGISource.VENUE_FALLBACK


def test_resolve_to_yahoo_venue_fallback_flag(tmp_path: Any) -> None:
    payload = _match(
        [
            _row("ACME", "GR", composite="DOMINANT"),
            _row("ACME", "US", composite="DOMINANT"),
        ]
    )
    res, _ = _resolver([FakeResponse(payload)], tmp_path)
    out = res.resolve_isin_to_yahoo_ticker("FR0000000000")
    assert out.yahoo_ticker == "ACME.DE"
    assert out.source is OpenFIGISource.VENUE_FALLBACK


# ------------------------------------------------------------ misses / flags


def test_resolve_to_yahoo_no_match(tmp_path: Any) -> None:
    res, _ = _resolver([FakeResponse([{"warning": "No identifier found."}])], tmp_path)
    out = res.resolve_isin_to_yahoo_ticker("XX0000000000")
    assert out.yahoo_ticker is None
    assert out.source is OpenFIGISource.NO_MATCH


def test_resolve_to_yahoo_unknown_exch(tmp_path: Any) -> None:
    # Country not mapped + venue absent from the suffix table → defensive flag.
    payload = _match([_row("ACME", "ZZ", composite="C1")])
    res, _ = _resolver([FakeResponse(payload)], tmp_path)
    out = res.resolve_isin_to_yahoo_ticker("QQ0000000000")
    assert out.yahoo_ticker is None
    assert out.exch_code_bbg == "ZZ"
    assert out.source is OpenFIGISource.UNKNOWN_EXCH


# ------------------------------------------------------- bbg_to_yahoo_suffix


@pytest.mark.parametrize(
    ("exch", "suffix"),
    [
        ("FP", ".PA"),
        ("XS", ".PA"),
        ("XH", ".PA"),
        ("EO", ".PA"),
        ("IM", ".MI"),
        ("GR", ".DE"),
        ("GY", ".DE"),
        ("NA", ".AS"),
        ("BB", ".BR"),
        ("SM", ".MC"),
        ("LN", ".L"),
    ],
)
def test_bbg_to_yahoo_suffix_known(exch: str, suffix: str) -> None:
    assert bbg_to_yahoo_suffix(exch) == suffix


def test_bbg_to_yahoo_suffix_unknown_returns_none() -> None:
    assert bbg_to_yahoo_suffix("ZZ") is None


# --------------------------------------------------------------------- batch


def test_resolve_batch_single_request(tmp_path: Any) -> None:
    body = [{"data": SANOFI[0]["data"]}, {"data": SAP[0]["data"]}]
    res, session = _resolver([FakeResponse(body)], tmp_path)
    out = res.resolve_batch(["FR0000120578", "DE0007164600"])
    assert out["FR0000120578"].yahoo_ticker == "SAN.PA"
    assert out["DE0007164600"].yahoo_ticker == "SAP.DE"
    assert len(session.calls) == 1  # both ISINs in one batched POST
    assert len(session.calls[0]) == 2


# --------------------------------------------------------------------- cache


def test_cache_hit_skips_network(tmp_path: Any) -> None:
    res, session = _resolver([FakeResponse(SANOFI)], tmp_path, use_cache=True)
    first = res.resolve_isin_to_yahoo_ticker("FR0000120578")
    second = res.resolve_isin_to_yahoo_ticker("FR0000120578")
    assert first == second
    assert len(session.calls) == 1  # second served from disk cache


def test_cache_miss_for_different_isin(tmp_path: Any) -> None:
    res, session = _resolver([FakeResponse(SANOFI), FakeResponse(SAP)], tmp_path, use_cache=True)
    res.resolve_isin_to_yahoo_ticker("FR0000120578")
    res.resolve_isin_to_yahoo_ticker("DE0007164600")
    assert len(session.calls) == 2


def test_cache_expiry_refetches(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    res, session = _resolver([FakeResponse(SANOFI), FakeResponse(SANOFI)], tmp_path, use_cache=True)
    res.resolve_isin_to_yahoo_ticker("FR0000120578")
    # Backdate the cached entry beyond TTL on disk + drop the in-memory copy.
    cache_file = tmp_path / "openfigi_cache.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    stale = (datetime.now(tz=UTC) - r.CACHE_TTL - timedelta(days=1)).isoformat()
    cache["FR0000120578"]["resolved_at"] = stale
    cache_file.write_text(json.dumps(cache), encoding="utf-8")
    res._cache = None  # force reload from disk
    res.resolve_isin_to_yahoo_ticker("FR0000120578")
    assert len(session.calls) == 2  # refetched after expiry


# ---------------------------------------------------------------- retries


def test_post_retries_then_succeeds(tmp_path: Any) -> None:
    res, session = _resolver(
        [FakeResponse(SANOFI, status_code=429), FakeResponse(SANOFI)], tmp_path
    )
    out = res.resolve_isin_to_yahoo_ticker("FR0000120578")
    assert out.yahoo_ticker == "SAN.PA"
    assert len(session.calls) == 2


# ------------------------------------------- Euronext Growth (Step 2.5)


@pytest.mark.parametrize(
    ("ticker", "expected"),
    [
        ("ALCLAEUR", "ALCLA"),  # currency suffix stripped
        ("AMPLIEUR", "AMPLI"),  # currency suffix stripped
        ("ALIDS", "ALIDS"),  # "IDS" is not a currency → kept
        ("MND1EUR", "MND1"),  # only EUR stripped; numeric disambiguator kept
        ("CBDG", "CBDG"),  # no currency suffix → kept
        ("COPCHF", "COP"),  # CHF stripped
        ("EUR", "EUR"),  # stem < 2 chars → not stripped (guard)
        ("ABEUR", "AB"),  # 2-char stem → stripped
    ],
)
def test_strip_currency_suffix(ticker: str, expected: str) -> None:
    assert strip_currency_suffix(ticker) == expected


def test_fr_growth_xs_resolves_to_pa(tmp_path: Any) -> None:
    # CLASQUIN: no FP row, only the XS EUR-composite row → ALCLA.PA.
    payload = _match([_row("ALCLAEUR", "XS", composite="BBG0058LYQG1")])
    res, _ = _resolver([FakeResponse(payload)], tmp_path)
    out = res.resolve_isin_to_yahoo_ticker("FR0004152882")
    assert out.yahoo_ticker == "ALCLA.PA"
    assert out.exch_code_bbg == "XS"
    # Growth venues are flagged LOW-confidence (BBG ticker != Yahoo symbol).
    assert out.source is OpenFIGISource.HOME_VENUE_GROWTH


def test_fr_growth_no_currency_suffix(tmp_path: Any) -> None:
    # CAMBODGE: EO/XS rows, ticker CBDG (no currency suffix) → CBDG.PA.
    payload = _match([_row("CBDG", "EO", composite="C1"), _row("CBDG", "XS", composite="C1")])
    res, _ = _resolver([FakeResponse(payload)], tmp_path)
    out = res.resolve_isin_to_yahoo_ticker("FR0000079659")
    assert out.yahoo_ticker == "CBDG.PA"
    assert out.source is OpenFIGISource.HOME_VENUE_GROWTH


def test_fr_prefers_fp_over_growth_venues() -> None:
    # When both a main-market (FP) and a Growth (XS) row exist, FP wins.
    rows = [
        OpenFIGIRow("ALCLAEUR", "XS", "Common Stock", "Equity", "C1", "S1", "X"),
        OpenFIGIRow("COVH", "FP", "REIT", "Equity", "C1", "S1", "X"),
    ]
    sel = select_home_venue(rows, "FR0000060303")
    assert sel is not None
    assert sel[1] == "FP"
    assert sel[3] is OpenFIGISource.HOME_VENUE


def test_post_raises_after_exhaustion(tmp_path: Any) -> None:
    responses = [FakeResponse([], status_code=503) for _ in range(1 + len(r.RETRY_BACKOFFS))]
    res, _ = _resolver(responses, tmp_path)
    with pytest.raises(RuntimeError, match="failed after"):
        res.resolve_isin("FR0000120578")
