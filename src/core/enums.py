"""Enum value catalogs — used for the Postgres ENUM types in migrations and
for typed Python-side validation in the ORM.

Per CLAUDE.md: enums live in Postgres as native ENUM types (not Python-side
enum classes coerced to strings), so we expose plain string literal tuples
and let SQLAlchemy `Enum(..., name=..., create_type=False)` reference them.
"""

from __future__ import annotations

from typing import Final, Literal

# ---- Jurisdictions -------------------------------------------------------

Jurisdiction = Literal["FR", "IT", "DE"]
JURISDICTIONS: Final[tuple[Jurisdiction, ...]] = ("FR", "IT", "DE")

# ---- Deal type (offer mechanism per jurisdiction) ------------------------

DealType = Literal[
    "OPA",  # Offre Publique d'Achat (FR cash)
    "OPE",  # Offre Publique d'Échange (FR exchange)
    "OPAS",  # OPA Simplifiée (FR)
    "OPR",  # Offre Publique de Retrait (FR squeeze-out)
    "OPRO",  # OPA Obligatoire (FR mandatory)
    "OPV",  # Offerta Pubblica Volontaria (IT)
    "OPVS",  # Offerta Pubblica Volontaria di Scambio (IT exchange)
    "OPA_IT",  # Offerta Pubblica di Acquisto obbligatoria (IT mandatory)
    "Uebernahmeangebot",  # Übernahmeangebot (DE control)
    "Pflichtangebot",  # Mandatory offer (DE)
    "Erwerbsangebot",  # Acquisition offer (DE non-control)
    "Delistingangebot",  # Delisting offer (DE)
]
DEAL_TYPES: Final[tuple[DealType, ...]] = (
    "OPA",
    "OPE",
    "OPAS",
    "OPR",
    "OPRO",
    "OPV",
    "OPVS",
    "OPA_IT",
    "Uebernahmeangebot",
    "Pflichtangebot",
    "Erwerbsangebot",
    "Delistingangebot",
)

# ---- Deal status ---------------------------------------------------------

DealStatus = Literal[
    "announced",
    "cleared",
    "open",
    "closed",
    "lapsed",
    "withdrawn",
]
DEAL_STATUSES: Final[tuple[DealStatus, ...]] = (
    "announced",
    "cleared",
    "open",
    "closed",
    "lapsed",
    "withdrawn",
)

# ---- Event type (CLAUDE.md §7 phase 1 + phase 5) -------------------------

EventType = Literal[
    "filing_amf",
    "filing_consob",
    "filing_bafin",
    "clearance",
    "extension",
    "waiver",
    "MAC",
    "court_ruling",
    "antitrust_decision",
    "FDI_decision",
    "FSR_decision",
    "news",
    "price_update",
    "shareholder_disclosure",
]
EVENT_TYPES: Final[tuple[EventType, ...]] = (
    "filing_amf",
    "filing_consob",
    "filing_bafin",
    "clearance",
    "extension",
    "waiver",
    "MAC",
    "court_ruling",
    "antitrust_decision",
    "FDI_decision",
    "FSR_decision",
    "news",
    "price_update",
    "shareholder_disclosure",
)

# ---- Scoring decision (CLAUDE.md §7 phase 7) -----------------------------

Decision = Literal["enter", "wait", "skip"]
DECISIONS: Final[tuple[Decision, ...]] = ("enter", "wait", "skip")

# ---- Analyst verdict (CLAUDE.md §7 phase 8) ------------------------------

AnalystVerdict = Literal["GO", "WAIT", "SKIP"]
ANALYST_VERDICTS: Final[tuple[AnalystVerdict, ...]] = ("GO", "WAIT", "SKIP")

# ---- Analyst source ------------------------------------------------------

AnalystSource = Literal["claude_opus_4_7", "manual"]
ANALYST_SOURCES: Final[tuple[AnalystSource, ...]] = ("claude_opus_4_7", "manual")

# ---- Position side / status ---------------------------------------------

PositionSide = Literal["long", "short"]
POSITION_SIDES: Final[tuple[PositionSide, ...]] = ("long", "short")

PositionStatus = Literal["open", "closed", "stopped"]
POSITION_STATUSES: Final[tuple[PositionStatus, ...]] = ("open", "closed", "stopped")

# ---- Currency (ISO 4217 — limit to relevant European currencies for phase 1) ----

Currency = Literal["EUR", "CHF", "GBP", "USD"]
CURRENCIES: Final[tuple[Currency, ...]] = ("EUR", "CHF", "GBP", "USD")

# ---- Price data source --------------------------------------------------

PriceSource = Literal["ibkr", "stooq"]
PRICE_SOURCES: Final[tuple[PriceSource, ...]] = ("ibkr", "stooq")
