"""P9.1a regression — BaFin offer_price re-anchoring (Bug 1) + mixed-offer
detection (Bug 2).

Asserts run on REAL BaFin cover-page excerpts in tests/fixtures/p91a/*_excerpt.txt
(the source PDFs are gitignored — see that directory's README.md). The excerpts
deliberately contain both the "Grundkapital ... EUR 1,00" par-value trap and the
real consideration clause, so they prove the parser anchors on the right one.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from src.ingestion.bafin.parser import _extract_offer

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "p91a"


def _excerpt(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- Bug 1: anchor on the cash clause, not the par value -------------------


def test_linus_extracts_1_76_not_grundkapital() -> None:
    price, currency, flag = _extract_offer(_excerpt("linus_1070_excerpt.txt"))
    assert price == Decimal("1.76")  # Geldbetrag, NOT the EUR 1,00 Grundkapital
    assert currency == "EUR"
    assert flag == "verified_cash"


def test_infas_extracts_6_80_not_grundkapital() -> None:
    price, currency, flag = _extract_offer(_excerpt("infas_1079_excerpt.txt"))
    assert price == Decimal("6.80")  # Geldleistung, NOT the EUR 1,00 Grundkapital
    assert currency == "EUR"
    assert flag == "verified_cash"


def test_philomaxcap_extracts_geldleistung_1_00() -> None:
    # Critical: the real offer genuinely IS EUR 1,00 (Geldbetrag). The parser
    # must find the cash clause, not coincidentally pick the par value — proves
    # anchoring works even when the two values collide.
    price, currency, flag = _extract_offer(_excerpt("philomaxcap_1080_excerpt.txt"))
    assert price == Decimal("1.00")
    assert currency == "EUR"
    assert flag == "verified_cash"


def test_klassik_extracts_gegenleistung_3_70() -> None:
    # Cash offer phrased "Gegenleistung in Höhe von EUR 3,70 je Aktie". The
    # backfill first nulled this (Gegenleistung was missing from the cash
    # anchor); singular "je Aktie" keeps it out of the mixed (plural "Aktien")
    # path, so it is correctly a cash offer.
    price, currency, flag = _extract_offer(_excerpt("klassik_1071_excerpt.txt"))
    assert price == Decimal("3.70")
    assert currency == "EUR"
    assert flag == "verified_cash"


# --- Bug 2: share-exchange / mixed offers carry no scalar price ------------


def test_commerzbank_flagged_suspect_mixed() -> None:
    # 0,485 UniCredit shares per Commerzbank share, no cash leg.
    price, currency, flag = _extract_offer(_excerpt("commerzbank_348_excerpt.txt"))
    assert price is None
    assert currency is None
    assert flag == "suspect_mixed"


def test_prosieben_flagged_suspect_mixed() -> None:
    # EUR 4,48 cash + 0,4 MFE shares — the cash leg must NOT be stored alone.
    price, currency, flag = _extract_offer(_excerpt("prosieben_1059_excerpt.txt"))
    assert price is None
    assert currency is None
    assert flag == "suspect_mixed"


def test_gegenleistung_share_exchange_stays_mixed() -> None:
    # Negative guard for the order: "Gegenleistung" is a cash keyword (Klassik),
    # but a share-exchange "Gegenleistung in Form von <ratio> Aktien der …" must
    # still resolve to suspect_mixed because the mixed check runs first. Protects
    # the mixed-before-cash ordering against future refactors.
    text = (
        "… der ZielTest AG gegen Gewährung einer Gegenleistung in Form von "
        "0,5 Aktien der Acquirer AG je Aktie der ZielTest AG …"
    )
    assert _extract_offer(text) == (None, None, "suspect_mixed")


# --- guards / fallbacks ----------------------------------------------------


def test_bare_grundkapital_is_not_captured_as_price() -> None:
    # The old bug returned 1.00 here; the anchored parser must return nothing.
    text = "Stückaktien mit einem anteiligen Betrag am Grundkapital von EUR 1,00 je Aktie."
    price, _currency, flag = _extract_offer(text)
    assert price is None
    assert flag == "suspect_low_unverified"


def test_no_offer_clause_falls_back_to_unverified() -> None:
    price, currency, flag = _extract_offer("Annahmefrist: 1. Januar 2026 bis 1. Februar 2026.")
    assert price is None
    assert currency is None
    assert flag == "suspect_low_unverified"
