"""AMF metadata extractor.

Phase 2 only does *basic* extraction; deep section parsing (intentions
initiateur, rapport expert, etc.) lands in phase 6.

Two layers:

1. `parse_title(title)` — pull out keywords from the RSS title:
   - canonical `deal_type` (one of the FR canonical enum values)
   - `target_name`, `acquirer_name` (best-effort, often missing in the title)

2. `extract_pdf_metadata(path)` — open the first 5 PDF pages with PyMuPDF
   and pull:
   - target/acquirer names if the title was inconclusive
   - `announcement_date` if visible
   - `offer_price` and `currency` if visible
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

import fitz  # PyMuPDF
import structlog

_log = structlog.get_logger(__name__)


# Mapping of legacy/spoken codes (as seen in RSS titles) to the canonical
# deal_type enum values from src.core.enums. Matched longest-first so that
# longer prefixes (e.g. "OPA SIMPLIFIÉE") win over the bare "OPA".
TITLE_TO_DEAL_TYPE: Final[dict[str, str]] = {
    # Long French forms (most common in AMF RSS titles)
    "OFFRE PUBLIQUE DE RETRAIT OBLIGATOIRE": "opr_ro",
    "OFFRE PUBLIQUE DE RETRAIT": "opr",
    "OFFRE PUBLIQUE D'ACHAT SIMPLIFIÉE": "opa_simplifiee",
    "OFFRE PUBLIQUE D'ACHAT SIMPLIFIEE": "opa_simplifiee",
    "OFFRE PUBLIQUE D'ACHAT": "opa",
    "OFFRE PUBLIQUE D'ÉCHANGE": "ope",
    "OFFRE PUBLIQUE D'ECHANGE": "ope",
    "OFFRE PUBLIQUE DE RACHAT": "opra",
    "GARANTIE DE COURS": "garantie_de_cours",
    # Short acronyms
    "OPA SIMPLIFIÉE": "opa_simplifiee",
    "OPA SIMPLIFIEE": "opa_simplifiee",
    "OPAS": "opa_simplifiee",
    "OPRA": "opra",
    "OPR-RO": "opr_ro",
    "OPR RO": "opr_ro",
    "OPR": "opr",
    "OPE": "ope",
    "OPA": "opa",
}

# Quick lookup for "is OPA mandatory?" — appears in titles like
# "OPA visant les actions… (offre obligatoire)" or "Note d'information OPRO".
_MANDATORY_HINT = re.compile(r"\b(obligatoire|mandatory)\b", re.IGNORECASE)

# French monetary literal. P9.2 02a: decimals are optional (integer prices like
# "28 €" or "10 000 €" must match) and the thousands separator now accepts any
# whitespace incl. NBSP (was a broken `[ \\xa0\.]` char class that matched the
# literal chars `\`, `x`, `a`, `0`, not the U+00A0 non-breaking space).
_PRICE_REGEX = re.compile(
    r"(?P<amount>\d{1,3}(?:[\s.]\d{3})*(?:[,\.]\d{1,4})?)\s*" r"(?P<currency>€|EUR|CHF|GBP|USD)",
    re.IGNORECASE,
)

# P9.2 02a: par-value / nominal-value exclusion. Mirror of the BaFin
# Grundkapital guard (P9.1a): a price preceded within ~80 chars by "valeur
# nominale" / "nominale unitaire" / "nominal" is the OCEANE par value, not the
# offer price (SELECTIRENTE 218C2043 case). Skip the match and continue.
_NOMINAL_VALUE_RE = re.compile(
    r"valeur\s+nominale|nominale?\s+unitaire|nominal",
    re.IGNORECASE,
)

# Date: "12 septembre 2024" or "12/09/2024" or "2024-09-12".
_FR_MONTHS: Final[dict[str, int]] = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}
_DATE_FR = re.compile(
    r"\b(?P<d>\d{1,2})\s+(?P<m>" + "|".join(_FR_MONTHS.keys()) + r")\s+(?P<y>\d{4})\b",
    re.IGNORECASE,
)
_DATE_SLASH = re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})\b")
_DATE_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b")


@dataclass(frozen=True, slots=True)
class ParsedMetadata:
    """The structured fields we can extract from a single AMF filing."""

    deal_type: str | None
    target_name: str | None
    acquirer_name: str | None
    announcement_date: date | None
    offer_price: Decimal | None
    currency: str | None
    raw_text_sample: str = ""

    def has_minimum(self) -> bool:
        """Enough info to insert a `deals` row? `deal_type` is the bare minimum."""
        return self.deal_type is not None


def parse_title(title: str) -> ParsedMetadata:
    """Extract whatever we can from the RSS title alone.

    Returns `ParsedMetadata` with `deal_type` set (if a keyword matches) and
    the other fields left as None; the PDF pass fills them in.
    """
    deal_type = _classify_deal_type_from_title(title)
    target = _extract_target_from_title(title)
    return ParsedMetadata(
        deal_type=deal_type,
        target_name=target,
        acquirer_name=None,
        announcement_date=None,
        offer_price=None,
        currency=None,
    )


def extract_pdf_metadata(pdf_path: Path, *, max_pages: int = 5) -> ParsedMetadata:
    """Open a PDF and pull metadata from the first `max_pages` pages.

    Robust to ill-formed PDFs: any PyMuPDF failure logs and returns a near-
    empty `ParsedMetadata` so the orchestrator can still insert a deal row
    based on the title alone.
    """
    try:
        text = _read_pdf_text(pdf_path, max_pages=max_pages)
    except Exception as exc:
        _log.warning("amf.pdf.read_failed", path=str(pdf_path), error=str(exc))
        return ParsedMetadata(
            deal_type=None,
            target_name=None,
            acquirer_name=None,
            announcement_date=None,
            offer_price=None,
            currency=None,
        )

    deal_type = _classify_deal_type_from_title(text[:2000])
    target = _extract_target_from_pdf_text(text)
    acquirer = _extract_acquirer_from_pdf_text(text)
    announcement = _extract_first_date(text)
    price, currency = _extract_first_price(text)

    return ParsedMetadata(
        deal_type=deal_type,
        target_name=target,
        acquirer_name=acquirer,
        announcement_date=announcement,
        offer_price=price,
        currency=currency,
        raw_text_sample=text[:1024],
    )


def merge(title_md: ParsedMetadata, pdf_md: ParsedMetadata) -> ParsedMetadata:
    """Combine title-derived and PDF-derived metadata.

    Title wins on `deal_type` and `target_name` if present (RSS titles are
    usually more reliable than scanned PDF text). PDF fills the rest.
    """
    return ParsedMetadata(
        deal_type=title_md.deal_type or pdf_md.deal_type,
        target_name=title_md.target_name or pdf_md.target_name,
        acquirer_name=pdf_md.acquirer_name or title_md.acquirer_name,
        announcement_date=pdf_md.announcement_date or title_md.announcement_date,
        offer_price=pdf_md.offer_price or title_md.offer_price,
        currency=pdf_md.currency or title_md.currency,
        raw_text_sample=pdf_md.raw_text_sample or title_md.raw_text_sample,
    )


# ----------------------------------------------------------------------- internal


def _read_pdf_text(pdf_path: Path, *, max_pages: int) -> str:
    """Open with fitz and concatenate text from the first `max_pages` pages."""
    pieces: list[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pieces.append(page.get_text("text") or "")
    return "\n".join(pieces)


def _classify_deal_type_from_title(text: str) -> str | None:
    """Match the longest keyword in TITLE_TO_DEAL_TYPE."""
    upper = text.upper()
    # Iterate in length-descending order so 'OPA SIMPLIFIÉE' wins over 'OPA'.
    for key in sorted(TITLE_TO_DEAL_TYPE.keys(), key=len, reverse=True):
        if key in upper:
            candidate = TITLE_TO_DEAL_TYPE[key]
            # Demote OPA → opa_obligatoire if "obligatoire" keyword present
            if candidate == "opa" and _MANDATORY_HINT.search(text):
                return "opa_obligatoire"
            return candidate
    return None


def _extract_target_from_title(title: str) -> str | None:
    """Capture the bit after 'visant les' / 'visant les actions' / etc."""
    m = re.search(
        r"visant les (?:actions|titres) (?:de\s+(?:la\s+société\s+)?)?"
        r"(?P<name>[A-ZÉÈÀÙÊÔ][\w&'\.\- ]{2,60})",
        title,
    )
    if m:
        return m.group("name").strip().rstrip(".")
    return None


def _extract_target_from_pdf_text(text: str) -> str | None:
    """Looks for 'Société visée', 'Cible:' patterns in the first pages."""
    m = re.search(
        r"(?:Soci[ée]t[ée]\s+vis[ée]e|Cible|Target)\s*[:\-]\s*"
        r"(?P<name>[A-ZÉÈÀÙÊÔ][\w&'\.\- ]{2,80})",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group("name").strip().rstrip(".")
    return None


def _extract_acquirer_from_pdf_text(text: str) -> str | None:
    """Looks for 'Initiateur', 'Offrant' patterns."""
    m = re.search(
        r"(?:Initiateur|Offrant|Bidder)\s*[:\-]\s*" r"(?P<name>[A-ZÉÈÀÙÊÔ][\w&'\.\- ]{2,80})",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group("name").strip().rstrip(".")
    return None


def _extract_first_date(text: str) -> date | None:
    """Returns the first date found in `text` using fr/iso/slash patterns."""
    m = _DATE_FR.search(text)
    if m:
        try:
            return date(int(m["y"]), _FR_MONTHS[m["m"].lower()], int(m["d"]))
        except (KeyError, ValueError):
            pass
    m = _DATE_ISO.search(text)
    if m:
        try:
            return date(int(m["y"]), int(m["m"]), int(m["d"]))
        except ValueError:
            pass
    m = _DATE_SLASH.search(text)
    if m:
        try:
            return date(int(m["y"]), int(m["m"]), int(m["d"]))
        except ValueError:
            pass
    return None


def _extract_first_price(text: str) -> tuple[Decimal | None, str | None]:
    """First (amount, currency) pair in the text, skipping nominal-value matches.

    P9.2 02a: iterates instead of single-search so a match preceded within ~80
    chars by 'valeur nominale' / 'nominale unitaire' (OCEANE par value, not the
    offer price) is skipped and the next candidate is considered. Mirrors the
    BaFin Grundkapital exclusion (P9.1a).
    """
    for m in _PRICE_REGEX.finditer(text):
        amount_start = m.start("amount")
        preceding = text[max(0, amount_start - 80) : amount_start]
        if _NOMINAL_VALUE_RE.search(preceding):
            continue
        raw = re.sub(r"\s", "", m.group("amount")).replace(",", ".")
        # If there are >1 dots, treat the last one as decimal separator.
        if raw.count(".") > 1:
            head, _, tail = raw.rpartition(".")
            raw = head.replace(".", "") + "." + tail
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            continue
        cur_raw = m.group("currency").upper()
        currency = "EUR" if cur_raw == "€" else cur_raw
        return (amount, currency)
    return (None, None)


__all__ = [
    "TITLE_TO_DEAL_TYPE",
    "ParsedMetadata",
    "extract_pdf_metadata",
    "merge",
    "parse_title",
]
