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
#
# Canonical lowercase legal terminology — replaces the v1 placeholder codes.
# FR (AMF):      opa, opa_simplifiee, opa_obligatoire, ope, opas, opra, opr,
#                opr_ro, garantie_de_cours
# IT (Consob):   opa_volontaire_totalitaria, opa_volontaire_parziale,
#                opa_consolidamento
# DE (BaFin):    pflichtangebot, freiwilliges_uebernahmeangebot,
#                erwerbsangebot, delisting_erwerbsangebot

DealType = Literal[
    # FR
    "opa",
    "opa_simplifiee",
    "opa_obligatoire",
    "ope",
    "opas",
    "opra",
    "opr",
    "opr_ro",
    "garantie_de_cours",
    # IT
    "opa_volontaire_totalitaria",
    "opa_volontaire_parziale",
    "opa_consolidamento",
    # DE
    "pflichtangebot",
    "freiwilliges_uebernahmeangebot",
    "erwerbsangebot",
    "delisting_erwerbsangebot",
]
DEAL_TYPES: Final[tuple[DealType, ...]] = (
    "opa",
    "opa_simplifiee",
    "opa_obligatoire",
    "opa_volontaire_totalitaria",
    "opa_volontaire_parziale",
    "opa_consolidamento",
    "ope",
    "opas",
    "opra",
    "opr",
    "opr_ro",
    "garantie_de_cours",
    "pflichtangebot",
    "freiwilliges_uebernahmeangebot",
    "delisting_erwerbsangebot",
    "erwerbsangebot",
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
