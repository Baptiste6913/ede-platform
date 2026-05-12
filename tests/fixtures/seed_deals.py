"""Seed dataset — 10 representative European M&A deals for phase 1 tests.

Coverage:
- 3 FR (AMF)         — OPA / OPAS / OPE
- 3 IT (Consob)      — OPV / OPVS / OPA_IT
- 3 DE (BaFin)       — Uebernahmeangebot / Pflichtangebot / Erwerbsangebot
- 1 cross-border DE  — Uebernahmeangebot whose target is dual-listed FR/DE

Statuses sample the full lifecycle: announced, cleared, open, closed,
lapsed, withdrawn.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

# Each dict is kwargs for `models.Deal(**deal)`. They intentionally exclude
# `id`, `created_at`, `updated_at` (DB defaults).
SEED_DEALS: list[dict[str, Any]] = [
    # ---- FR -----------------------------------------------------------
    {
        "juridiction": "FR",
        "regulator_ref": "AMF-2024-D-0421",
        "ticker_target": "ALGOL.PA",
        "ticker_acquirer": "BIDR.PA",
        "target_name": "Algol SA",
        "acquirer_name": "Bidder Holding France",
        "announcement_date": date(2024, 9, 12),
        "deal_type": "OPA",
        "status": "open",
        "offer_price": Decimal("28.50"),
        "currency": "EUR",
        "payment_cash_share": Decimal("1.0000"),
        "premium_pct": Decimal("0.1800"),
        "min_acceptance_threshold": Decimal("0.6667"),
        "expected_close_date": date(2024, 12, 20),
        "source_url": "https://www.amf-france.org/fr/.../AMF-2024-D-0421",
    },
    {
        "juridiction": "FR",
        "regulator_ref": "AMF-2024-S-0033",
        "ticker_target": "BETAFR.PA",
        "ticker_acquirer": None,  # squeeze-out via subsidiary, ticker irrelevant
        "target_name": "Beta France",
        "acquirer_name": "ParentCo Group SAS",
        "announcement_date": date(2024, 4, 3),
        "deal_type": "OPAS",
        "status": "closed",
        "offer_price": Decimal("12.10"),
        "currency": "EUR",
        "payment_cash_share": Decimal("1.0000"),
        "premium_pct": Decimal("0.0500"),
        "min_acceptance_threshold": Decimal("0.9000"),
        "expected_close_date": date(2024, 5, 30),
        "source_url": "https://www.amf-france.org/fr/.../AMF-2024-S-0033",
    },
    {
        "juridiction": "FR",
        "regulator_ref": "AMF-2024-E-0019",
        "ticker_target": "GAMMA.PA",
        "ticker_acquirer": "DELTA.PA",
        "target_name": "Gamma Industries",
        "acquirer_name": "Delta Group",
        "announcement_date": date(2024, 7, 22),
        "deal_type": "OPE",
        "status": "announced",
        "offer_price": None,
        "currency": "EUR",
        "payment_cash_share": Decimal("0.0000"),
        "premium_pct": Decimal("0.2200"),
        "min_acceptance_threshold": Decimal("0.5000"),
        "expected_close_date": date(2025, 2, 14),
        "source_url": "https://www.amf-france.org/fr/.../AMF-2024-E-0019",
    },
    # ---- IT -----------------------------------------------------------
    {
        "juridiction": "IT",
        "regulator_ref": "CONSOB-OPA-2024-018",
        "ticker_target": "EPSILON.MI",
        "ticker_acquirer": "ZETACO.MI",
        "target_name": "Epsilon SpA",
        "acquirer_name": "Zeta Holding Italia",
        "announcement_date": date(2024, 6, 5),
        "deal_type": "OPV",
        "status": "cleared",
        "offer_price": Decimal("5.20"),
        "currency": "EUR",
        "payment_cash_share": Decimal("1.0000"),
        "premium_pct": Decimal("0.2500"),
        "min_acceptance_threshold": Decimal("0.6667"),
        "expected_close_date": date(2024, 9, 30),
        "source_url": "https://www.consob.it/.../OPA-2024-018",
    },
    {
        "juridiction": "IT",
        "regulator_ref": "CONSOB-OPA-2024-007",
        "ticker_target": "ETA.MI",
        "ticker_acquirer": "THETA.MI",
        "target_name": "Eta Manifatturiera",
        "acquirer_name": "Theta Industriale",
        "announcement_date": date(2024, 2, 18),
        "deal_type": "OPVS",
        "status": "withdrawn",
        "offer_price": None,
        "currency": "EUR",
        "payment_cash_share": Decimal("0.5000"),
        "premium_pct": Decimal("0.1500"),
        "min_acceptance_threshold": Decimal("0.6667"),
        "expected_close_date": date(2024, 5, 31),
        "source_url": "https://www.consob.it/.../OPA-2024-007",
    },
    {
        "juridiction": "IT",
        "regulator_ref": "CONSOB-OPA-2024-022",
        "ticker_target": "IOTA.MI",
        "ticker_acquirer": "KAPPA.MI",
        "target_name": "Iota Energia SpA",
        "acquirer_name": "Kappa Power SpA",
        "announcement_date": date(2024, 10, 14),
        "deal_type": "OPA_IT",
        "status": "open",
        "offer_price": Decimal("3.75"),
        "currency": "EUR",
        "payment_cash_share": Decimal("1.0000"),
        "premium_pct": Decimal("0.0900"),
        "min_acceptance_threshold": Decimal("0.6667"),
        "expected_close_date": date(2025, 1, 31),
        "source_url": "https://www.consob.it/.../OPA-2024-022",
    },
    # ---- DE -----------------------------------------------------------
    {
        "juridiction": "DE",
        "regulator_ref": "BAFIN-WPUEG-2024-031",
        "ticker_target": "LAMBDA.DE",
        "ticker_acquirer": "MU.DE",
        "target_name": "Lambda Maschinenbau AG",
        "acquirer_name": "Mu Industrieholding GmbH",
        "announcement_date": date(2024, 8, 7),
        "deal_type": "Uebernahmeangebot",
        "status": "cleared",
        "offer_price": Decimal("44.80"),
        "currency": "EUR",
        "payment_cash_share": Decimal("1.0000"),
        "premium_pct": Decimal("0.2800"),
        "min_acceptance_threshold": Decimal("0.5000"),
        "expected_close_date": date(2024, 11, 15),
        "source_url": "https://www.bafin.de/.../WPUEG-2024-031",
    },
    {
        "juridiction": "DE",
        "regulator_ref": "BAFIN-WPUEG-2024-014",
        "ticker_target": "NU.DE",
        "ticker_acquirer": "XI.DE",
        "target_name": "Nu Chemie AG",
        "acquirer_name": "Xi Bidder GmbH",
        "announcement_date": date(2024, 3, 28),
        "deal_type": "Pflichtangebot",
        "status": "closed",
        "offer_price": Decimal("18.20"),
        "currency": "EUR",
        "payment_cash_share": Decimal("1.0000"),
        "premium_pct": Decimal("0.0000"),  # mandatory at min price
        "min_acceptance_threshold": None,  # mandatory has no threshold
        "expected_close_date": date(2024, 5, 20),
        "source_url": "https://www.bafin.de/.../WPUEG-2024-014",
    },
    {
        "juridiction": "DE",
        "regulator_ref": "BAFIN-WPUEG-2024-009",
        "ticker_target": "OMICRON.DE",
        "ticker_acquirer": None,
        "target_name": "Omicron Pharma AG",
        "acquirer_name": "Pi PE Partners",
        "announcement_date": date(2024, 1, 22),
        "deal_type": "Erwerbsangebot",
        "status": "lapsed",
        "offer_price": Decimal("9.95"),
        "currency": "EUR",
        "payment_cash_share": Decimal("1.0000"),
        "premium_pct": Decimal("0.1100"),
        "min_acceptance_threshold": Decimal("0.5000"),
        "expected_close_date": date(2024, 4, 30),
        "source_url": "https://www.bafin.de/.../WPUEG-2024-009",
    },
    # ---- Cross-border (DE filing, FR/DE dual-listed target) ----------
    {
        "juridiction": "DE",
        "regulator_ref": "BAFIN-WPUEG-2024-040",
        "ticker_target": "RHO.DE",  # also listed RHO.PA
        "ticker_acquirer": "SIGMA.DE",
        "target_name": "Rho Technologies SE",
        "acquirer_name": "Sigma Capital SE",
        "announcement_date": date(2024, 11, 4),
        "deal_type": "Uebernahmeangebot",
        "status": "announced",
        "offer_price": Decimal("62.00"),
        "currency": "EUR",
        "payment_cash_share": Decimal("0.7500"),
        "premium_pct": Decimal("0.3200"),
        "min_acceptance_threshold": Decimal("0.7500"),
        "expected_close_date": date(2025, 3, 14),
        "source_url": "https://www.bafin.de/.../WPUEG-2024-040",
    },
]

assert len(SEED_DEALS) == 10, "seed must contain exactly 10 deals"


def expected_count_by_jurisdiction() -> dict[str, int]:
    """Helper for tests: assert the FR/IT/DE distribution."""
    counts: dict[str, int] = {}
    for d in SEED_DEALS:
        key = d["juridiction"]
        counts[key] = counts.get(key, 0) + 1
    return counts
