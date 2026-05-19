"""Best-effort metadata extraction from a Consob `documento d'offerta` PDF.

Phase 4 scope: pull only the most reliable fields that can be regex'd off
the first few pages (offer_price, currency, announcement_date, opening_date,
closing_date_est, official_visa). Deep section-by-section parsing
(Sezione G — Modalità e termini, etc.) is deferred to phase 6/7.

Italian regex patterns are conservative — we'd rather skip a field than
record a wrong value (the analyst LLM in phase 8 can fill gaps).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

import fitz
import structlog

_log = structlog.get_logger(__name__)

_IT_MONTHS: Final[dict[str, int]] = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

_DATE_IT_RE = re.compile(
    r"\b(?P<d>\d{1,2})\s+(?P<m>" + "|".join(_IT_MONTHS.keys()) + r")\s+(?P<y>\d{4})\b",
    re.IGNORECASE,
)
_DATE_SLASH_RE = re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})\b")

# Italian money: "Euro 28,50", "EUR 28,50", "€ 28,50", "28,50 euro/EUR/€"
_PRICE_RE = re.compile(
    r"(?:(?:Euro|EUR|€)\s*(?P<amount1>\d{1,3}(?:[ .]\d{3})*[,.]\d{2,4}))"
    r"|(?:(?P<amount2>\d{1,3}(?:[ .]\d{3})*[,.]\d{2,4})\s*(?:Euro|EUR|€))",
    re.IGNORECASE,
)

# Official Consob visa: "Comunicazione n. XXXXX del DD/MM/YYYY".
_COMUNICAZIONE_RE = re.compile(
    r"Comunicazione\s+n\.?\s*(?P<num>[\w\-/]+)\s+del\s+(?P<day>\d{1,2})[\s/\.\-]+"
    r"(?P<month>\d{1,2}|" + "|".join(_IT_MONTHS.keys()) + r")[\s/\.\-]+(?P<year>\d{4})",
    re.IGNORECASE,
)

# Period of adhesion: "dal DD mese YYYY al DD mese YYYY"
_PERIODO_RE = re.compile(
    r"dal\s+(?P<d1>\d{1,2})\s+(?P<m1>"
    + "|".join(_IT_MONTHS.keys())
    + r")\s+(?P<y1>\d{4})\s+al\s+(?P<d2>\d{1,2})\s+(?P<m2>"
    + "|".join(_IT_MONTHS.keys())
    + r")\s+(?P<y2>\d{4})",
    re.IGNORECASE,
)

# Initiator: "Offerente: NOME" or "Offerente NOME ..."
_OFFERENTE_RE = re.compile(r"Offerente[\s:]+(?P<name>[A-ZÀÉÈÌÒÙ][\w&'\.\- ]{2,80})", re.IGNORECASE)
# Target: "Società oggetto: NOME" or "Emittente NOME"
_TARGET_RE = re.compile(
    r"(?:Societ[àa]\s+oggetto|Emittente|Societ[àa]\s+target)[\s:]+"
    r"(?P<name>[A-ZÀÉÈÌÒÙ][\w&'\.\- ]{2,80})",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ParsedConsobMetadata:
    """Fields recovered from the PDF body. All optional — the listing-level
    `OpaRecord` is the source of truth for `consob_ref`, `target_name`,
    `offerente_name`, `deal_type`."""

    official_visa: str | None
    announcement_date: date | None
    opening_date: date | None
    closing_date_est: date | None
    offer_price: Decimal | None
    currency: str | None
    target_name_from_pdf: str | None
    offerente_name_from_pdf: str | None
    raw_text_sample: str = ""

    def has_minimum(self) -> bool:
        return any(
            (
                self.official_visa,
                self.announcement_date,
                self.opening_date,
                self.offer_price,
            )
        )


def extract_pdf_metadata(pdf_path: Path, *, max_pages: int = 5) -> ParsedConsobMetadata:
    """Open `pdf_path`, read `max_pages` pages, regex out the canonical fields."""
    try:
        text = _read_pdf_text(pdf_path, max_pages=max_pages)
    except Exception as exc:
        _log.warning("consob.pdf.read_failed", path=str(pdf_path), error=str(exc))
        return ParsedConsobMetadata(
            official_visa=None,
            announcement_date=None,
            opening_date=None,
            closing_date_est=None,
            offer_price=None,
            currency=None,
            target_name_from_pdf=None,
            offerente_name_from_pdf=None,
        )

    visa, visa_date = _extract_visa(text)
    period_start, period_end = _extract_periodo(text)
    price, currency = _extract_price(text)
    target = _extract_first(_TARGET_RE, text)
    offerente = _extract_first(_OFFERENTE_RE, text)

    return ParsedConsobMetadata(
        official_visa=visa,
        announcement_date=visa_date,
        opening_date=period_start,
        closing_date_est=period_end,
        offer_price=price,
        currency=currency,
        target_name_from_pdf=target,
        offerente_name_from_pdf=offerente,
        raw_text_sample=text[:1024],
    )


# --------------------------------------------------------------------- internals


def _read_pdf_text(pdf_path: Path, *, max_pages: int) -> str:
    pieces: list[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pieces.append(page.get_text("text") or "")
    return "\n".join(pieces)


def _extract_visa(text: str) -> tuple[str | None, date | None]:
    m = _COMUNICAZIONE_RE.search(text)
    if not m:
        return (None, None)
    num = m.group("num")
    visa = f"Comunicazione n. {num}"
    try:
        day = int(m.group("day"))
        month_raw = m.group("month").lower()
        month = int(month_raw) if month_raw.isdigit() else _IT_MONTHS.get(month_raw)
        year = int(m.group("year"))
        if month is None:
            return (visa, None)
        return (visa, date(year, month, day))
    except (ValueError, KeyError):
        return (visa, None)


def _extract_periodo(text: str) -> tuple[date | None, date | None]:
    m = _PERIODO_RE.search(text)
    if not m:
        return (None, None)
    try:
        start = date(
            int(m.group("y1")),
            _IT_MONTHS[m.group("m1").lower()],
            int(m.group("d1")),
        )
        end = date(
            int(m.group("y2")),
            _IT_MONTHS[m.group("m2").lower()],
            int(m.group("d2")),
        )
        return (start, end)
    except (KeyError, ValueError):
        return (None, None)


def _extract_price(text: str) -> tuple[Decimal | None, str | None]:
    m = _PRICE_RE.search(text)
    if not m:
        return (None, None)
    raw = m.group("amount1") or m.group("amount2") or ""
    normalised = raw.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        amount = Decimal(normalised)
    except InvalidOperation:
        return (None, None)
    return (amount, "EUR")


def _extract_first(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    name = m.group("name").strip().rstrip(".,;:")
    return re.sub(r"\s+", " ", name) or None


__all__ = [
    "ParsedConsobMetadata",
    "extract_pdf_metadata",
]
