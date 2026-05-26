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
    "opa_volontaria_preventiva",  # Phase 5 migration 0007 — IT future use
    # DE
    "pflichtangebot",
    "freiwilliges_uebernahmeangebot",
    "erwerbsangebot",
    "delisting_erwerbsangebot",
    # Cross-jurisdiction (Phase 5 migration 0007)
    "delisting_offer",
    # DE — BaFin Untersagung rows (Phase 6 Step-0 extension migration 0008).
    # Ingested as standalone deals (1 per Untersagung row) so they can later
    # be matched to a prior deal via ISIN+bieter heuristic (tech debt P7).
    "prohibition_ungenutzt",
]
DEAL_TYPES: Final[tuple[DealType, ...]] = (
    "opa",
    "opa_simplifiee",
    "opa_obligatoire",
    "opa_volontaire_totalitaria",
    "opa_volontaire_parziale",
    "opa_consolidamento",
    "opa_volontaria_preventiva",
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
    "delisting_offer",
    "prohibition_ungenutzt",
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

# ---- Offer-price quality flag (Phase 9.1a/c — BaFin parser + pricing) ----
#
# Provenance / confidence of the deal's offer price. Stored as TEXT + CHECK
# (migration 0015 converted it from the 0014 Postgres ENUM — TEXT is cheaper to
# evolve; this tuple is the canonical value list for the CHECK + validation).
#   verified_cash          — anchored on a cash clause
#                            ("Geldleistung/Geldbetrag … EUR X je Aktie"),
#                            not the share par value (Grundkapital EUR 1,00).
#   verified_mixed         — share/cash+share offer whose economic value was
#                            recomputed (cash_eur + share_ratio x acquirer quote)
#                            into offer_price_total_eur (P9.1c).
#   suspect_mixed          — share-exchange or cash+share offer detected
#                            ("Gewährung/Gegenleistung … Aktien der …"); not yet
#                            priced — awaiting the P9.1c recalc.
#   suspect_low_unverified — legacy / not yet re-parsed; the default.
#   failed_validation      — failed an external price cross-check (P9.1c).
#   manual_review          — escalated to a human.

OfferPriceQualityFlag = Literal[
    "verified_cash",
    "verified_mixed",
    "suspect_mixed",
    "suspect_low_unverified",
    "failed_validation",
    "manual_review",
]
OFFER_PRICE_QUALITY_FLAGS: Final[tuple[OfferPriceQualityFlag, ...]] = (
    "verified_cash",
    "verified_mixed",
    "suspect_mixed",
    "suspect_low_unverified",
    "failed_validation",
    "manual_review",
)

# ---- Pricing source (Phase 9.1c) ----------------------------------------
#
# How offer_price_total_eur was obtained. TEXT + CHECK (not a Postgres ENUM):
#   parser_only        — only the parser's cash leg; no external enrichment.
#   yfinance_enriched  — total recomputed via a yfinance acquirer/spot quote.
#   manual_override    — set by hand (operator).

PricingSource = Literal["parser_only", "yfinance_enriched", "manual_override"]
PRICING_SOURCES: Final[tuple[PricingSource, ...]] = (
    "parser_only",
    "yfinance_enriched",
    "manual_override",
)
