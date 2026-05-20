"""BaFin discovery client — parses the Angebotsunterlagen listing HTML.

The single monolithic page at

    https://www.bafin.de/DE/die-bafin/publikationen-daten/databanken-uebersichten/
    WPUeG/angebotsunterlagen/angebotsunterlagen_node.html

contains one `<table class="data">` with 5 columns per row:
    Bieter | Zielgesellschaft | ISIN | <a>Angebotsunterlage</a> | Veröffentlichung am

The `<a>` link text encodes the legal offer type (Übernahmeangebot,
Pflichtangebot, Erwerbsangebot, Teilerwerbsangebot, Delisting-…); we
map those to the canonical `DEAL_TYPES` enum. `Untersagung` (regulatory
prohibition) is **filtered out** at this layer because it is not an
offer.

The dedup key is `BAFIN-{ISIN-no-spaces}-{YYYYMMDD}` per Step-0 spec
(robust against slug collisions; the actual `nn=` query-string ID is
opaque and would require an extra wrapper fetch to extract).
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

import httpx
import structlog
from bs4 import BeautifulSoup, Tag

from src.core.settings import get_settings

if TYPE_CHECKING:
    pass

_log = structlog.get_logger(__name__)

LISTING_URL = (
    "https://www.bafin.de/DE/die-bafin/publikationen-daten/datenbanken-uebersichten/"
    "WPUeG/angebotsunterlagen/angebotsunterlagen_node.html"
)

# Browser-class headers — BaFin returns 404 to obvious bot UAs.
LISTING_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
}

# German offer-type narrative → canonical DEAL_TYPES enum.
# Ordered longest-first so "Delisting-Erwerbsangebot" matches before "Erwerbsangebot".
GERMAN_TYPE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"delisting[-\s]?erwerbsangebot", re.IGNORECASE), "delisting_offer"),
    (re.compile(r"delisting[-\s]?übernahmeangebot", re.IGNORECASE), "delisting_offer"),
    (re.compile(r"delisting[-\s]?pflichtangebot", re.IGNORECASE), "delisting_offer"),
    (re.compile(r"delisting[-\s]?rückerwerbsangebot", re.IGNORECASE), "delisting_offer"),
    (re.compile(r"teilerwerbsangebot", re.IGNORECASE), "opa_volontaire_parziale"),
    (
        re.compile(r"pflichtangebot\s*/\s*erwerbsangebot", re.IGNORECASE),
        "opa_obligatoire",
    ),
    (re.compile(r"übernahmeangebot", re.IGNORECASE), "opa_volontaire_totalitaria"),
    (re.compile(r"pflichtangebot", re.IGNORECASE), "opa_obligatoire"),
    (
        re.compile(r"erwerbsangebot\s+änderung", re.IGNORECASE),
        # Amendments will become events in phase 7. Discovery currently
        # ingests them as the parent offer type so dedup catches them.
        "opa_volontaire_parziale",
    ),
    (re.compile(r"erwerbsangebot", re.IGNORECASE), "opa_volontaire_parziale"),
)

# Rows we explicitly skip — these are not deals.
SKIPPED_NARRATIVES: tuple[re.Pattern[str], ...] = (re.compile(r"untersagung", re.IGNORECASE),)

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_NAME_MAX_LEN = 120
_NAME_TAILS = re.compile(
    r"\s*(?:,|\(|\bz\.\s*Hd\.\b|\bvertreten\b|\bhandelnd\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class AngebotsunterlageRecord:
    """One row of the BaFin Angebotsunterlagen listing."""

    bafin_ref: str
    bieter_name: str
    target_name: str
    target_isin: str | None
    offer_type_raw: str  # raw German narrative as shown on the listing
    deal_type: str | None  # canonical DEAL_TYPES (None if unmapped)
    wrapper_url: str
    veroeffentlichung_date: date
    is_amendment: bool = False
    discovered_at: datetime = field(
        default_factory=lambda: datetime.now(tz=datetime.now().astimezone().tzinfo or None)
    )


# --------------------------------------------------------------------------- HTML parsing


def parse_listing(html: str) -> list[AngebotsunterlageRecord]:
    """Extract every `AngebotsunterlageRecord` from the listing HTML."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="data")
    if not isinstance(table, Tag):
        _log.warning("bafin.discovery.no_data_table")
        return []

    records: list[AngebotsunterlageRecord] = []
    rows = table.find_all("tr")
    for tr in rows[1:]:  # skip header
        if not isinstance(tr, Tag):
            continue
        record = _parse_row(tr)
        if record is not None:
            records.append(record)
    return records


def _parse_row(tr: Tag) -> AngebotsunterlageRecord | None:
    tds = tr.find_all("td")
    if len(tds) != 5:  # noqa: PLR2004 — fixed BaFin table shape
        return None

    bieter_raw = tds[0].get_text(" ", strip=True)
    target_raw = tds[1].get_text(" ", strip=True)
    isin_raw = tds[2].get_text(strip=True)
    link = tds[3].find("a")
    if not isinstance(link, Tag):
        return None
    offer_type_raw = link.get_text(" ", strip=True)
    href = link.get("href")
    if not isinstance(href, str):
        return None
    date_raw = tds[4].get_text(strip=True)

    # Filter regulatory prohibitions etc.
    if any(p.search(offer_type_raw) for p in SKIPPED_NARRATIVES):
        _log.info(
            "bafin.discovery.row.skipped",
            reason="non_offer_narrative",
            offer_type=offer_type_raw,
            bieter=bieter_raw,
            target=target_raw,
        )
        return None

    veroeffentlichung = _parse_date(date_raw)
    if veroeffentlichung is None:
        _log.warning("bafin.discovery.row.bad_date", date_raw=date_raw)
        return None

    isin = _normalize_isin(isin_raw)
    deal_type = _classify_deal_type(offer_type_raw)
    bafin_ref = _derive_bafin_ref(isin=isin, when=veroeffentlichung, fallback=href)
    wrapper_url = (
        href if href.startswith("http") else urllib.parse.urljoin("https://www.bafin.de", href)
    )

    return AngebotsunterlageRecord(
        bafin_ref=bafin_ref,
        bieter_name=_trim_company_name(bieter_raw),
        target_name=_trim_company_name(target_raw),
        target_isin=isin,
        offer_type_raw=offer_type_raw,
        deal_type=deal_type,
        wrapper_url=wrapper_url,
        veroeffentlichung_date=veroeffentlichung,
        is_amendment=bool(re.search(r"änderung", offer_type_raw, re.IGNORECASE)),
    )


def _parse_date(text: str) -> date | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _normalize_isin(text: str) -> str | None:
    """Strip whitespace inside the ISIN ("DE000 CBK1001" → "DE000CBK1001").

    Returns None if the result doesn't match the ISO 6166 shape.
    """
    candidate = re.sub(r"\s+", "", text).upper()
    if _ISIN_RE.match(candidate):
        return candidate
    return None


def _classify_deal_type(narrative: str) -> str | None:
    for pattern, deal_type in GERMAN_TYPE_RULES:
        if pattern.search(narrative):
            return deal_type
    return None


def _derive_bafin_ref(*, isin: str | None, when: date, fallback: str) -> str:
    """Stable dedup key: `BAFIN-{ISIN}-{YYYYMMDD}`.

    When the ISIN is missing or malformed (rare on BaFin), fall back to
    `BAFIN-{wrapper-slug}-{YYYYMMDD}` so the row still has a unique key.
    """
    if isin:
        return f"BAFIN-{isin}-{when.strftime('%Y%m%d')}"
    parsed = urllib.parse.urlparse(fallback)
    slug_match = re.search(r"/([a-zA-Z0-9_\-]+)\.html", parsed.path)
    slug = slug_match.group(1).lower() if slug_match else "unknown"
    return f"BAFIN-{slug}-{when.strftime('%Y%m%d')}"


def _trim_company_name(name: str) -> str:
    text = re.sub(r"\s+", " ", name).strip().rstrip(".,;: ")
    m = _NAME_TAILS.search(text)
    if m:
        text = text[: m.start()].rstrip(".,;: ")
    if len(text) > _NAME_MAX_LEN:
        text = text[:_NAME_MAX_LEN].rstrip()
    return text


# ------------------------------------------------------------------- async iterator


class BafinDiscoveryClient:
    """High-level async iterator over the Angebotsunterlagen listing."""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        *,
        listing_url: str = LISTING_URL,
    ) -> None:
        settings = get_settings()
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.poller_amf_timeout_seconds),
            follow_redirects=True,
            headers=LISTING_HEADERS,
        )
        self._listing_url = listing_url

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def iter_all(
        self,
        *,
        since: date | None = None,
    ) -> AsyncIterator[AngebotsunterlageRecord]:
        """Yield every `AngebotsunterlageRecord`. Drops rows whose
        `veroeffentlichung_date` is older than `since` (when provided)."""
        resp = await self._client.get(self._listing_url)
        resp.raise_for_status()
        records = parse_listing(resp.text)
        _log.info(
            "bafin.discovery.page",
            rows=len(records),
            since=since.isoformat() if since else None,
        )
        for record in records:
            if since is not None and record.veroeffentlichung_date < since:
                continue
            yield record
