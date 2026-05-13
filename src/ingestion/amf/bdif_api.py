"""AMF BDIF API client.

Talks to the public-but-undocumented `GET /back/api/v1/informations` endpoint
that powers the Recherche avancée page at https://bdif.amf-france.org.

Discovered in phase 3 (see `docs/research/bdif-api-reverse-engineering.md`):
- no auth required as long as the request looks like a desktop browser
  (User-Agent, Accept-Language, Referer)
- pagination via `From` / `Size` (ES-style)
- M&A documents = `typesInformation=OPA` + `typesDocument=NotesEtAutresInformations`
- absolute PDF URL = `/back/api/v1/documents/{item.documents[0].path}`
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import httpx
import structlog

from src.core.settings import get_settings
from src.ingestion.amf.rate_limiter import RateLimiter, retry_with_backoff

_log = structlog.get_logger(__name__)

BDIF_BASE_URL = "https://bdif.amf-france.org"
BDIF_SEARCH_PATH = "/back/api/v1/informations"
BDIF_DOCUMENT_PATH = "/back/api/v1/documents"

# Mapping from `typesOperation` (raw API value) to our canonical deal_type enum.
# Documented in docs/research/bdif-api-reverse-engineering.md §7.
OPERATION_TO_DEAL_TYPE: dict[str, str] = {
    "OPA": "opa",
    "OPAS": "opa_simplifiee",
    "OPE": "ope",
    "OPES": "ope",  # OPE simplifiée — fold into OPE
    "OPR": "opr",
    "OPRA": "opra",
    "OPRRO": "opr_ro",
    "OPAGC": "garantie_de_cours",
    "RO": "opr_ro",
    "PreOffre": "opa",  # pre-offer signals usually convert into an OPA
}


@dataclass(frozen=True, slots=True)
class BdifSociete:
    """A counterparty referenced in a BDIF item."""

    jeton: str
    raison_sociale: str
    role: str  # e.g. SocieteVisee, Initiateur, SocieteConcernee


@dataclass(frozen=True, slots=True)
class BdifDocumentFile:
    """A downloadable PDF attached to a BDIF item."""

    nom_fichier: str
    path: str
    accessible: bool

    @property
    def absolute_url(self) -> str:
        return f"{BDIF_BASE_URL}{BDIF_DOCUMENT_PATH}/{self.path}"


@dataclass(frozen=True, slots=True)
class BdifItem:
    """Parsed BDIF search result item."""

    id: int
    numero: str  # acts as `regulator_ref`
    domaine: str | None
    types_information: tuple[str, ...]
    types_document: tuple[str, ...]
    types_operation: tuple[str, ...]
    date_information: datetime | None
    date_publication: datetime | None
    societes: tuple[BdifSociete, ...]
    documents: tuple[BdifDocumentFile, ...]
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def target_name(self) -> str | None:
        for s in self.societes:
            if s.role == "SocieteVisee":
                return s.raison_sociale
        for s in self.societes:
            if s.role == "SocieteConcernee":
                return s.raison_sociale
        return None

    @property
    def acquirer_name(self) -> str | None:
        for s in self.societes:
            if s.role == "Initiateur":
                return s.raison_sociale
        return None

    @property
    def primary_operation(self) -> str | None:
        return self.types_operation[0] if self.types_operation else None

    @property
    def deal_type(self) -> str | None:
        op = self.primary_operation
        return OPERATION_TO_DEAL_TYPE.get(op) if op else None

    @property
    def announcement_date(self) -> date | None:
        if self.date_information:
            return self.date_information.date()
        if self.date_publication:
            return self.date_publication.date()
        return None

    @property
    def first_pdf(self) -> BdifDocumentFile | None:
        for doc in self.documents:
            if doc.accessible:
                return doc
        return None


def parse_item(payload: dict[str, Any]) -> BdifItem:
    """Convert a raw API response dict into a `BdifItem`. Tolerates missing keys."""

    def _to_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    raw_societes = payload.get("societes") or []
    societes = tuple(
        BdifSociete(
            jeton=str(s.get("jeton", "")),
            raison_sociale=str(s.get("raisonSociale", "")).strip(),
            role=str(s.get("role", "")),
        )
        for s in raw_societes
    )
    raw_docs = payload.get("documents") or []
    documents = tuple(
        BdifDocumentFile(
            nom_fichier=str(d.get("nomFichier", "")),
            path=str(d.get("path", "")),
            accessible=bool(d.get("accessible", False)),
        )
        for d in raw_docs
        if d.get("path")
    )
    return BdifItem(
        id=int(payload.get("id", 0) or 0),
        numero=str(payload.get("numero", "")).strip(),
        domaine=str(payload.get("domaine", "")) or None,
        types_information=tuple(payload.get("typesInformation") or []),
        types_document=tuple(payload.get("typesDocument") or []),
        types_operation=tuple(payload.get("typesOperation") or []),
        date_information=_to_dt(payload.get("dateInformation")),
        date_publication=_to_dt(payload.get("datePublication")),
        societes=societes,
        documents=documents,
        raw=payload,
    )


class BdifApiClient:
    """Thin async wrapper around the BDIF search API."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: RateLimiter,
        *,
        max_retries: int | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._rate_limiter = rate_limiter
        self._max_retries = (
            max_retries if max_retries is not None else settings.poller_amf_max_retries
        )

    async def search_page(
        self,
        *,
        types_information: tuple[str, ...] = ("OPA",),
        types_document: tuple[str, ...] = ("NotesEtAutresInformations",),
        types_operation: tuple[str, ...] = (),
        offset: int = 0,
        size: int = 50,
    ) -> tuple[list[BdifItem], int]:
        """Fetch one page and return `(items, total_matching)`.

        Repeated query keys (httpx accepts a list of (key, value) tuples) are
        used for filters that are repeatable in the underlying ES query.
        """
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("From", offset),
            ("Size", size),
        ]
        for v in types_information:
            params.append(("typesInformation", v))
        for v in types_document:
            params.append(("typesDocument", v))
        for v in types_operation:
            params.append(("typesOperation", v))

        await self._rate_limiter.acquire()
        body = await retry_with_backoff(
            lambda: self._get_json(params),
            max_retries=self._max_retries,
            service="amf-bdif",
        )
        total = int(body.get("total") or 0)
        items = [parse_item(row) for row in (body.get("result") or [])]
        _log.info(
            "amf.bdif.page",
            offset=offset,
            size=size,
            total=total,
            returned=len(items),
        )
        return items, total

    async def _get_json(
        self,
        params: list[tuple[str, str | int | float | bool | None]],
    ) -> dict[str, Any]:
        resp = await self._client.get(
            f"{BDIF_BASE_URL}{BDIF_SEARCH_PATH}",
            params=params,
            headers={
                "Accept": "application/json",
                "Referer": f"{BDIF_BASE_URL}/fr",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            from src.core.exceptions import ExternalServiceError

            raise ExternalServiceError("amf-bdif", "unexpected JSON shape (not a dict)")
        return data

    async def iter_all(
        self,
        *,
        types_information: tuple[str, ...] = ("OPA",),
        types_document: tuple[str, ...] = ("NotesEtAutresInformations",),
        types_operation: tuple[str, ...] = (),
        page_size: int = 50,
        max_items: int | None = None,
    ) -> AsyncIterator[BdifItem]:
        """Yield matching items across pages, up to `max_items`."""
        offset = 0
        yielded = 0
        while True:
            items, total = await self.search_page(
                types_information=types_information,
                types_document=types_document,
                types_operation=types_operation,
                offset=offset,
                size=page_size,
            )
            for item in items:
                yield item
                yielded += 1
                if max_items is not None and yielded >= max_items:
                    return
            if not items or len(items) < page_size:
                return
            offset += page_size
            if offset >= total:
                return
