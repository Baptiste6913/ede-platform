"""Consob discovery client — parses the documenti-opa listing HTML.

Each `<li>` (non-header) in `<ul class="consobResult">` carries:
- `<div class="div20 center">` with start + end dates of the offer period
- `<div class="div80 j">` with a narrative description (offerente, target,
  prezzo, type in Italian text) and one or more `<a class="linkList">` PDF
  links inside `<span class="pdf">`.

`OpaRecord.consob_ref` is derived from the PDF URL slug:
    https://www.consob.it/documents/.../opa_bancasistema_20260511.pdf/{uuid}…
                                                ^^^^^^^^^^^^^^^^^^^^^^^^
                                                → consob_ref = "CONSOB-bancasistema-20260511"

This gives us a deterministic, human-readable, dedup-safe identifier even
before the PDF body parser extracts the official "numero d'ordine" (a
phase 6-7 enrichment).
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

import structlog
from bs4 import BeautifulSoup, Tag

from src.core.settings import get_settings

if TYPE_CHECKING:
    from src.ingestion.consob.scrapingbee_client import ScrapingBeeClient

_log = structlog.get_logger(__name__)

LISTING_URL = "https://www.consob.it/web/area-pubblica/documenti-opa"
LISTING_URL_TEMPLATE = (
    LISTING_URL
    + "?p_p_id=it_consob_OpaDocumentsPortlet&p_p_lifecycle=0&p_p_state=normal"
    + "&p_p_mode=view&_it_consob_OpaDocumentsPortlet_delta={delta}"
    + "&_it_consob_OpaDocumentsPortlet_resetCur=false"
    + "&_it_consob_OpaDocumentsPortlet_cur={cur}"
)

# Maps a raw Italian offer-type narrative to our canonical enum.
# Order matters — longest / most specific first.
#
# The canonical enum (src/core/enums.DEAL_TYPES, set in migration 0004)
# already carries Italian-themed values for the IT regulator:
#   opa_obligatoire                (covers obbligatoria + residuale)
#   opa_volontaire_totalitaria     (covers volontaria totalitaria + preventiva)
#   opa_volontaire_parziale        (covers volontaria parziale)
#   opa_consolidamento             (covers consolidamento — rare)
#   opas                           (covers acquisto e scambio)
ITALIAN_TYPE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"acquisto\s+e\s+scambio", re.IGNORECASE), "opas"),
    (re.compile(r"di\s+scambio", re.IGNORECASE), "opas"),
    (re.compile(r"consolidamento", re.IGNORECASE), "opa_consolidamento"),
    (re.compile(r"residuale", re.IGNORECASE), "opa_obligatoire"),
    (re.compile(r"obbligatoria", re.IGNORECASE), "opa_obligatoire"),
    (re.compile(r"volontaria\s+totalitaria", re.IGNORECASE), "opa_volontaire_totalitaria"),
    (re.compile(r"volontaria\s+parziale", re.IGNORECASE), "opa_volontaire_parziale"),
    (re.compile(r"volontaria\s+preventiva", re.IGNORECASE), "opa_volontaire_totalitaria"),
    (re.compile(r"volontaria", re.IGNORECASE), "opa_volontaire_totalitaria"),
)

# Extract offerente + target from the narrative.
_OFFERENTE_RE = re.compile(
    r"promossa\s+da\s+(?:<strong>)?([^<]+?)(?:</strong>)?\b(?:\s+(?:su|avente|in adesione))",
    re.IGNORECASE,
)
_TARGET_RE = re.compile(
    r"(?:emesse\s+da|su\s+azioni(?:\s+ordinarie)?\s+(?:emesse\s+da|di)|"
    r"avente\s+(?:ad\s+oggetto|per\s+oggetto)(?:\s+azioni|.*?azioni)?\s+(?:di|emesse\s+da)|"
    r"sulle\s+azioni\s+(?:ordinarie\s+)?(?:di|emesse\s+da))\s+"
    r"(?:<strong>)?([^<\.]+?)(?:</strong>)?(?:\s*\.|\s*\(|\s*$)",
    re.IGNORECASE,
)

_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_PDF_SLUG_RE = re.compile(r"/([a-zA-Z0-9_\-]+)\.pdf(?:/[a-f0-9-]+)?(?:\?|$)")


@dataclass(frozen=True, slots=True)
class OpaRecord:
    """One row of the documenti-opa listing, ready for downstream fetch + parse."""

    consob_ref: str  # stable dedup key, derived from PDF URL slug
    period_start: date | None
    period_end: date | None
    description: str
    target_name: str | None
    offerente_name: str | None
    deal_type: str | None
    documento_offerta_url: str | None
    additional_links: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    page_number: int = 1
    discovered_at: datetime = field(
        default_factory=lambda: datetime.now(tz=datetime.now().astimezone().tzinfo or None)
    )


# --------------------------------------------------------------------------- HTML parsing


def parse_listing(html: str, *, page_number: int = 1) -> list[OpaRecord]:
    """Extract every `OpaRecord` from a single page of the Consob listing."""
    soup = BeautifulSoup(html, "lxml")
    ul = soup.find("ul", class_="consobResult")
    if not isinstance(ul, Tag):
        _log.warning("consob.discovery.no_consobResult_ul")
        return []

    records: list[OpaRecord] = []
    for li in ul.find_all("li", recursive=False):
        if not isinstance(li, Tag):
            continue
        classes = li.get("class") or []
        if "header" in classes:
            continue
        record = _parse_row(li, page_number=page_number)
        if record is not None:
            records.append(record)
    return records


def _parse_row(li: Tag, *, page_number: int) -> OpaRecord | None:
    period_div = li.find("div", class_="div20")
    detail_div = li.find("div", class_="div80")
    if not isinstance(detail_div, Tag):
        return None

    start_date, end_date = _extract_period(period_div)
    description = _description_text(detail_div)
    target_name = _extract_target(detail_div, description)
    offerente_name = _extract_offerente(detail_div, description)
    deal_type = _classify_deal_type(description)
    doc_url, additional = _extract_links(detail_div)

    consob_ref = _derive_consob_ref(
        doc_url,
        fallback_target=target_name,
        fallback_offerente=offerente_name,
        fallback_start=start_date,
    )
    if consob_ref is None:
        # Skip silently; the row is too thin to dedup safely.
        _log.info("consob.discovery.row.skipped", reason="no_ref", target=target_name)
        return None

    return OpaRecord(
        consob_ref=consob_ref,
        period_start=start_date,
        period_end=end_date,
        description=description,
        target_name=target_name,
        offerente_name=offerente_name,
        deal_type=deal_type,
        documento_offerta_url=doc_url,
        additional_links=tuple(additional),
        page_number=page_number,
    )


def _extract_period(period_div: Tag | None) -> tuple[date | None, date | None]:
    if not isinstance(period_div, Tag):
        return (None, None)
    text = " ".join(period_div.stripped_strings)
    dates: list[date] = []
    for m in _DATE_RE.finditer(text):
        try:
            dates.append(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
        except ValueError:
            continue
    start = dates[0] if dates else None
    end = dates[1] if len(dates) > 1 else None
    return (start, end)


def _description_text(detail_div: Tag) -> str:
    # All <p> children — preserve narrative spaces but collapse runs of WS.
    paragraphs = [p.get_text(" ", strip=True) for p in detail_div.find_all("p")]
    text = " ".join(p for p in paragraphs if p)
    return re.sub(r"\s+", " ", text).strip()


_STRONG_OFFERENTE_IDX = 0  # 1st <strong> is the offerente
_STRONG_TARGET_IDX = 1  # 2nd <strong> is the target


def _extract_target(detail_div: Tag, description: str) -> str | None:
    # Prefer the 2nd <strong> in the description paragraph (heuristic from
    # Step 0 fixture: offerente is 1st <strong>, target is 2nd <strong>).
    strongs = detail_div.find_all("strong")
    if len(strongs) > _STRONG_TARGET_IDX:
        text = strongs[_STRONG_TARGET_IDX].get_text(" ", strip=True)
        if text:
            return _trim_company_name(text)
    # Fallback to regex on description text.
    m = _TARGET_RE.search(description)
    if m:
        return _trim_company_name(m.group(1).strip())
    return None


def _extract_offerente(detail_div: Tag, description: str) -> str | None:
    strongs = detail_div.find_all("strong")
    if strongs:
        text = strongs[0].get_text(" ", strip=True)
        if text:
            return _trim_company_name(text)
    m = _OFFERENTE_RE.search(description)
    if m:
        return _trim_company_name(m.group(1).strip())
    return None


def _classify_deal_type(description: str) -> str | None:
    for pattern, deal_type in ITALIAN_TYPE_RULES:
        if pattern.search(description):
            return deal_type
    return None


def _extract_links(detail_div: Tag) -> tuple[str | None, list[tuple[str, str]]]:
    """Returns (documento_offerta_url, additional_links)."""
    span_pdf = detail_div.find("span", class_="pdf")
    if not isinstance(span_pdf, Tag):
        return (None, [])
    doc_url: str | None = None
    additional: list[tuple[str, str]] = []
    for a in span_pdf.find_all("a"):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if not isinstance(href, str):
            continue
        text = a.get_text(" ", strip=True)
        if doc_url is None and "documento d'offerta" in text.lower():
            doc_url = href
        else:
            additional.append((text, href))
    return (doc_url, additional)


def _derive_consob_ref(
    doc_url: str | None,
    *,
    fallback_target: str | None,
    fallback_offerente: str | None,
    fallback_start: date | None,
) -> str | None:
    """Stable dedup key.

    First choice: `CONSOB-{filename-without-extension}` from the PDF URL.
    Fallback: `CONSOB-{slug(target)}-{slug(offerente)}-{YYYYMMDD}` if no
    PDF link exists yet (rare — comunicato-only rows).
    """
    if doc_url:
        m = _PDF_SLUG_RE.search(urllib.parse.urlparse(doc_url).path)
        if m:
            slug = m.group(1)
            return f"CONSOB-{slug}"
    parts: list[str] = []
    if fallback_target:
        parts.append(_slugify(fallback_target))
    if fallback_offerente:
        parts.append(_slugify(fallback_offerente))
    if fallback_start:
        parts.append(fallback_start.strftime("%Y%m%d"))
    if not parts:
        return None
    return "CONSOB-" + "-".join(parts)


def _trim_company_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().rstrip(".,;:")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


# ------------------------------------------------------------------- async iterator


class ConsobDiscoveryClient:
    """High-level iterator over the documenti-opa listing pages."""

    def __init__(self, scrapingbee: ScrapingBeeClient, *, page_size: int = 50) -> None:
        settings = get_settings()
        self._sb = scrapingbee
        self._page_size = page_size
        self._listing_template = LISTING_URL_TEMPLATE
        _ = settings  # placeholder for future per-jurisdiction toggles

    async def iter_all(self, *, max_pages: int | None = None) -> AsyncIterator[OpaRecord]:
        """Yield every `OpaRecord` discovered until pages run out or
        `max_pages` is reached. Pagination stops automatically when a
        page returns fewer than `page_size` rows."""
        page = 1
        while True:
            if max_pages is not None and page > max_pages:
                return
            url = self._listing_template.format(delta=self._page_size, cur=page)
            resp = await self._sb.get(url)
            records = parse_listing(resp.text, page_number=page)
            _log.info(
                "consob.discovery.page",
                page=page,
                rows=len(records),
                cost=resp.credits_cost,
            )
            for record in records:
                yield record
            if len(records) < self._page_size:
                return
            page += 1
