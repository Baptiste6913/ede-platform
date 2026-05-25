"""Best-effort metadata extraction from a BaFin Angebotsunterlage PDF.

Phase 5 scope: pull only the most reliable fields that can be regex'd
off the first ~10 pages — Bieter, Zielgesellschaft, Annahmefrist
(opening + closing dates), Angebotspreis (EUR). Deeper section-by-section
parsing (`§4 Mindestpreisangebot`, `§6 Bedingungen`) is deferred to
phase 6/7. German regex patterns are conservative — better to skip a
field than record a wrong value.

Phase 9.1a: `offer_price` is re-anchored on the cash-consideration clause
("Geldleistung/Geldbetrag/Angebotspreis ... EUR X je Aktie") instead of the
first EUR amount in the document — which on German Stückaktien is the per-share
par value ("anteiliger Betrag am Grundkapital ... EUR 1,00") and was being
recorded as the offer (Bug 1). Each parse now carries an
`offer_price_quality_flag` and a `parser_version`.
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

# Bumped whenever the extraction logic changes so backfills can target stale
# rows (`deals.parser_version < PARSER_VERSION`). P9.1a = version 2.
PARSER_VERSION: Final[int] = 2

# German month names (case-insensitive). Both full forms ("März") and
# common abbreviations ("Mrz", "März" sometimes shown as "Maerz").
_DE_MONTHS: Final[dict[str, int]] = {
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "märz": 3,
    "maerz": 3,
    "mrz": 3,
    "mär": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "oktober": 10,
    "okt": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
}

_MONTH_PATTERN = "|".join(sorted(_DE_MONTHS.keys(), key=len, reverse=True))

_DATE_DE_RE = re.compile(
    r"(?P<d>\d{1,2})\.\s*(?P<m>" + _MONTH_PATTERN + r")\s*(?P<y>\d{4})",
    re.IGNORECASE,
)
_DATE_DOTTED_RE = re.compile(r"(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})")

# "Annahmefrist: vom 01. März 2026 bis zum 30. April 2026"
# Also: "Beginn der Annahmefrist: 01.03.2026 / Ende der Annahmefrist: 30.04.2026"
_ANNAHMEFRIST_VOM_BIS = re.compile(
    r"(?:vom|von)\s+(?P<d1>\d{1,2})\.\s*(?P<m1>"
    + _MONTH_PATTERN
    + r")\s*(?P<y1>\d{4})\s+(?:bis(?:\s+zum)?)\s+(?P<d2>\d{1,2})\.\s*(?P<m2>"
    + _MONTH_PATTERN
    + r")\s*(?P<y2>\d{4})",
    re.IGNORECASE,
)
_ANNAHMEFRIST_DOTTED = re.compile(
    r"Annahmefrist[\s\S]{0,80}?(?P<d1>\d{1,2})\.(?P<m1>\d{1,2})\.(?P<y1>\d{4})"
    r"[\s\S]{0,80}?(?P<d2>\d{1,2})\.(?P<m2>\d{1,2})\.(?P<y2>\d{4})",
    re.IGNORECASE,
)

# A German money amount: "28,50", "1.234,56", "1 234,56". Decimal comma.
_AMOUNT = r"\d{1,3}(?:[ .]\d{3})*[,.]\d{2,4}"

# Offer price ANCHORED on a cash-consideration clause. This is deliberately NOT
# a bare "EUR x,xx" search (the P9.1a Bug 1): German Stückaktien state a
# per-share par value ("anteiliger Betrag am Grundkapital ... EUR 1,00") near
# the top, and a first-match search recorded that instead of the real price.
# Handles both "EUR 6,80" and "12,00 EUR" orders and the line breaks BaFin
# inserts between the clause and the amount.
#
# "Gegenleistung" is included: some BaFin offers phrase the cash price as
# "Gegenleistung in Höhe von EUR X je Aktie" (e.g. Klassik Radio). This does not
# clash with the share-exchange use of the same word ("Gegenleistung von X
# Aktien der ...") because the mixed check runs FIRST and keys on plural
# "Aktien der", whereas a cash clause ends in singular "je Aktie".
_OFFER_CASH_RE = re.compile(
    r"(?:Angebotspreis|Angebotsgegenleistung|Gegenleistung|Barangebot|Geldleistung|Geldbetrag)\w*"
    r"[\s:]+(?:in\s+Höhe\s+von\s+|von\s+)?"
    r"(?:EUR\s*(?P<a1>" + _AMOUNT + r")|(?P<a2>" + _AMOUNT + r")\s*EUR)",
    re.IGNORECASE,
)

# Par-value / share-capital markers. Belt-and-suspenders guard: reject a cash
# match whose amount is glued to one of these (the keyword anchor above already
# excludes the "Grundkapital ... EUR 1,00" sentence, which carries no cash verb).
_PAR_VALUE_RE = re.compile(
    r"Grundkapital|Nennbetrag|Nennwert|anteilige[rmn]?\s+Betrag|rechnerische[rmn]?\s+Anteil",
    re.IGNORECASE,
)

# Mixed / share-exchange consideration (P9.1a Bug 2): "Gewährung/Gegenleistung
# (von) <ratio> (Stück)aktien [Klasse] der <Erwerber>". Covers ProSieben (EUR
# 4,48 cash + 0,4 MFE shares) and Commerzbank (0,485 UniCredit shares, no cash).
# Such offers cannot be reduced to a scalar EUR price — structuring the cash +
# share legs is P9.1b.
_OFFER_MIXED_RE = re.compile(
    r"(?:Gewährung|Gegenleistung)\s+(?:von\s+)?"
    r"(?P<ratio>\d{1,3}(?:[.,]\d+)?)\s+"
    r"(?:Stück)?[Aa]ktien(?:\s+[A-Z])?\s+der\s+\w+",
    re.IGNORECASE,
)

# Bidder / target labels — BaFin templates use either German or capitalised forms.
_BIETER_RE = re.compile(
    r"Bieter(?:in)?\s*[:\-]?\s*(?P<name>[A-ZÄÖÜ][^\n]{2,120})",
    re.IGNORECASE,
)
_ZIEL_RE = re.compile(
    r"Zielgesellschaft\s*[:\-]?\s*(?P<name>[A-ZÄÖÜ][^\n]{2,120})",
    re.IGNORECASE,
)
_OFFER_TYPE_RE = re.compile(
    r"\b(Übernahmeangebot|Pflichtangebot|Teilerwerbsangebot|Erwerbsangebot|"
    r"Delisting[-\s]?Erwerbsangebot|Delisting[-\s]?Übernahmeangebot|"
    r"Delisting[-\s]?Pflichtangebot)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ParsedBafinMetadata:
    """Fields recovered from the PDF body. All optional — the listing-level
    `AngebotsunterlageRecord` is the source of truth for `bafin_ref`,
    `target_name`, `bieter_name`, `deal_type`."""

    opening_date: date | None
    closing_date_est: date | None
    offer_price: Decimal | None
    currency: str | None
    target_name_from_pdf: str | None
    bieter_name_from_pdf: str | None
    offer_type_from_pdf: str | None
    raw_text_sample: str = ""
    # Phase 9.1a — provenance of offer_price + the parser revision that set it.
    offer_price_quality_flag: str = "suspect_low_unverified"
    parser_version: int = PARSER_VERSION

    def has_minimum(self) -> bool:
        return any((self.opening_date, self.offer_price, self.bieter_name_from_pdf))


def extract_pdf_metadata(pdf_path: Path, *, max_pages: int = 10) -> ParsedBafinMetadata:
    try:
        text = _read_pdf_text(pdf_path, max_pages=max_pages)
    except Exception as exc:
        _log.warning("bafin.pdf.read_failed", path=str(pdf_path), error=str(exc))
        return ParsedBafinMetadata(
            opening_date=None,
            closing_date_est=None,
            offer_price=None,
            currency=None,
            target_name_from_pdf=None,
            bieter_name_from_pdf=None,
            offer_type_from_pdf=None,
        )

    opening, closing = _extract_annahmefrist(text)
    price, currency, quality_flag = _extract_offer(text)
    target = _extract_first(_ZIEL_RE, text)
    bieter = _extract_first(_BIETER_RE, text)
    offer_type = _extract_offer_type(text)

    return ParsedBafinMetadata(
        opening_date=opening,
        closing_date_est=closing,
        offer_price=price,
        currency=currency,
        target_name_from_pdf=target,
        bieter_name_from_pdf=bieter,
        offer_type_from_pdf=offer_type,
        raw_text_sample=text[:1024],
        offer_price_quality_flag=quality_flag,
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


def _parse_de_date(d: str, m: str, y: str) -> date | None:
    try:
        month = int(m) if m.isdigit() else _DE_MONTHS[m.lower()]
        return date(int(y), month, int(d))
    except (ValueError, KeyError):
        return None


def _extract_annahmefrist(text: str) -> tuple[date | None, date | None]:
    m = _ANNAHMEFRIST_VOM_BIS.search(text)
    if m:
        start = _parse_de_date(m.group("d1"), m.group("m1"), m.group("y1"))
        end = _parse_de_date(m.group("d2"), m.group("m2"), m.group("y2"))
        if start or end:
            return (start, end)
    m = _ANNAHMEFRIST_DOTTED.search(text)
    if m:
        start = _parse_de_date(m.group("d1"), m.group("m1"), m.group("y1"))
        end = _parse_de_date(m.group("d2"), m.group("m2"), m.group("y2"))
        return (start, end)
    return (None, None)


def _extract_offer(text: str) -> tuple[Decimal | None, str | None, str]:
    """Return (offer_price, currency, quality_flag).

    Order matters. A mixed / share-exchange offer is detected FIRST and yields
    NO scalar price ('suspect_mixed'): these offers also carry a cash leg
    (ProSieben EUR 4,48 + 0,4 shares) that must not be stored as the price
    (Bug 2). A clean cash offer yields a price + 'verified_cash'. Otherwise the
    price stays NULL with 'suspect_low_unverified' — never the par value, which
    was the Bug-1 behaviour.
    """
    if _OFFER_MIXED_RE.search(text):
        return (None, None, "suspect_mixed")
    price = _extract_cash_price(text)
    if price is not None:
        return (price, "EUR", "verified_cash")
    return (None, None, "suspect_low_unverified")


def _extract_cash_price(text: str) -> Decimal | None:
    for m in _OFFER_CASH_RE.finditer(text):
        amount_start = m.start("a1") if m.group("a1") else m.start("a2")
        preceding = text[max(0, amount_start - 30) : amount_start]
        if _PAR_VALUE_RE.search(preceding):
            continue  # amount glued to a par-value clause — not the offer
        raw = m.group("a1") or m.group("a2") or ""
        normalised = raw.replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return Decimal(normalised)
        except InvalidOperation:
            continue
    return None


def _extract_first(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    name = m.group("name").strip().rstrip(".,;:")
    # Cut at first hard delimiter — labels often run into "Zielgesellschaft: X\nBieter: Y"
    name = re.split(r"\s*(?:Bieter|Zielgesellschaft|Angebot|ISIN)\b", name, maxsplit=1)[0]
    return re.sub(r"\s+", " ", name).strip().rstrip(".,;:") or None


def _extract_offer_type(text: str) -> str | None:
    m = _OFFER_TYPE_RE.search(text)
    if not m:
        return None
    return m.group(1)


__all__ = [
    "PARSER_VERSION",
    "ParsedBafinMetadata",
    "extract_pdf_metadata",
]
