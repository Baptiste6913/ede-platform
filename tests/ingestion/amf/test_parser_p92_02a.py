"""P9.2 02a regression — AMF integer-price regex + NBSP + valeur-nominale guard.

Three changes are tested here:

1. **Integer prices**: the original ``_PRICE_REGEX`` required ``[,\\.]\\d{2,4}`` so
   bare "28 €" / "82 €" silently missed. Decimals are now optional.
2. **NBSP thousands separator**: the original char class ``[ \\\\xa0\\.]`` matched
   the literal chars ``\\``/``x``/``a``/``0`` instead of U+00A0. Switched to
   ``[\\s.]`` so "101 382,00" (with NBSP) parses correctly.
3. **valeur nominale exclusion**: a price preceded within ~80 chars by
   "valeur nominale" / "nominale unitaire" is the OCEANE par value, not the
   offer price (SELECTIRENTE 218C2043). Mirrors the BaFin Grundkapital guard
   from P9.1a.

The 3 known false positives that remain (TESSI 160, FNAC DARTY 36 x2) are
documented in :func:`test_known_false_positives_deferred_02b` — they require
positional anchoring, deferred to commit #2b.
"""

from __future__ import annotations

from decimal import Decimal

from src.ingestion.amf.parser import _extract_first_price

# --- 1. Positive cases (integer prices, formerly silent_miss) --------------


def test_tipiak_82_euro() -> None:
    """TIPIAK 224C0830 — bare integer 'prix unitaire de 82 €'."""
    text = (
        "tions TIPIAK représentant 77,53% du capital de la société3 au prix "
        "unitaire de 82 € et a franchi, a cette même date, les seuils"
    )
    price, currency = _extract_first_price(text)
    assert price == Decimal("82")
    assert currency == "EUR"


def test_prodware_28_euro() -> None:
    """PRODWARE 225C2156 — 'prix unitaire de 28 € par action'."""
    text = (
        "L'initiateur s'engage irrévocablement à acquérir, au prix unitaire "
        "de 28 € par action, la totalité des actions PRODWARE"
    )
    price, currency = _extract_first_price(text)
    assert price == Decimal("28")
    assert currency == "EUR"


def test_altur_11_euro() -> None:
    """ALTUR INVESTISSEMENT 223C1897 — 'prix unitaire de 11 €'."""
    text = (
        "L'initiateur s'engage irrévocablement à acquérir, au prix unitaire "
        "de 11 €, la totalité des 587 538 actions ALTUR"
    )
    price, currency = _extract_first_price(text)
    assert price == Decimal("11")
    assert currency == "EUR"


def test_tarkett_20_euro() -> None:
    """TARKETT 221C0878 — 'prix de 20 € par action'."""
    text = (
        "L'initiateur s'engage irrévocablement à acquérir, au prix de 20 € "
        "par action, la totalité des 32 185 572 actions"
    )
    price, currency = _extract_first_price(text)
    assert price == Decimal("20")
    assert currency == "EUR"


def test_pcas_8_euro() -> None:
    """PCAS 223C1382 — 'prix unitaire de 8 €'."""
    text = (
        "L'initiateur s'engage irrévocablement à acquérir, au prix unitaire "
        "de 8 €, la totalité des 3 534 073 actions PCAS"
    )
    price, currency = _extract_first_price(text)
    assert price == Decimal("8")
    assert currency == "EUR"


# --- 2. Non-regression: decimal prices must still match -------------------


def test_cegid_61_00_euro() -> None:
    """CEGID GROUP 216C1735 — preserves two-decimal price."""
    text = "au prix de 61,00 € par action CEGID GROUP"
    price, currency = _extract_first_price(text)
    assert price == Decimal("61.00")
    assert currency == "EUR"


def test_neoen_39_85_euro() -> None:
    """NEOEN 225C0021 — preserves two-decimal price."""
    text = "au prix unitaire de 39,85 € par action NEOEN"
    price, currency = _extract_first_price(text)
    assert price == Decimal("39.85")
    assert currency == "EUR"


def test_tayninh_0_11_euro() -> None:
    """SOCIETE DE TAYNINH 225C2081 — preserves sub-unit price."""
    text = "au prix unitaire de 0,11 € par action"
    price, currency = _extract_first_price(text)
    assert price == Decimal("0.11")
    assert currency == "EUR"


# --- 3. NBSP thousands separator -----------------------------------------


def test_neoen_oceane_nbsp_101_382() -> None:
    """NEOEN OCEANE — '101\\xa0382,00 €' (NBSP between 101 and 382) must parse."""
    text = "valeur de remboursement de 101\xa0382,00 € par OCEANE"
    # Preceded by "valeur de" not "valeur nominale", so the nominal guard
    # does NOT trigger and the price must be returned.
    price, currency = _extract_first_price(text)
    assert price == Decimal("101382.00")
    assert currency == "EUR"


# --- 4. True negative controls (must not match) ---------------------------


def test_no_match_percentage() -> None:
    """'prime de 25 %' has no currency suffix → no match."""
    text = "représentant une prime de 25 % par rapport au cours moyen"
    price, currency = _extract_first_price(text)
    assert price is None
    assert currency is None


def test_no_match_calendar_date() -> None:
    """'le 15 mars 2024' — digits not followed by currency → no match."""
    text = "Le 15 mars 2024, l'AMF a déclaré conforme le projet d'offre."
    price, currency = _extract_first_price(text)
    assert price is None
    assert currency is None


def test_no_match_article_number() -> None:
    """'article 231-1' — no currency suffix → no match."""
    text = "en application de l'article 231-1 du règlement général"
    price, currency = _extract_first_price(text)
    assert price is None
    assert currency is None


# --- 5. valeur nominale exclusion (SELECTIRENTE 218C2043) ----------------


def test_valeur_nominale_excluded() -> None:
    """SELECTIRENTE 218C2043 — OCEANE par value 63 € must NOT be returned as
    offer price. The phrase 'valeur nominale unitaire' within 80 chars before
    the amount triggers the exclusion (mirror of BaFin Grundkapital guard).
    """
    text = (
        "l'AMF le 26 novembre 2013 sous le n°13-631), d'une valeur "
        "nominale unitaire de 63 €, d'échéance le 1er janvier 2020"
    )
    price, currency = _extract_first_price(text)
    assert price is None
    assert currency is None


# --- 6. Known false positives deferred to commit #2b -----------------------


def test_known_false_positives_deferred_02b() -> None:
    """Documents the CURRENT (wrong) extraction for the three known FPs that
    require positional anchoring of the principal commitment clause —
    deferred to commit #2b.

    This test pins the behaviour so a future fix breaks it on purpose
    (correct prices listed in the assertion message). DO NOT 'fix' these
    in this commit; the regex changes here are scoped to integer prices,
    NBSP, and nominal-value exclusion only.
    """
    # TESSI 219C0051 — extracts the second mention (160 €) instead of the
    # actual offer price (42.70 €) because the regex returns the first
    # finditer hit and the 160 € sentence precedes the real clause.
    tessi = (
        "TESSI qu'il ne détient pas, soit 1 277 567 actions TESSI2, au prix "
        "unitaire de 160 euros (le dividende exceptionnel et l'acomp"
    )
    price, _ = _extract_first_price(tessi)
    assert price == Decimal("160"), "deferred to 02b: real TESSI offer is 42.70"

    # FNAC DARTY 226C0287 — extracts 36 € (a residual mention) instead of
    # the actual offer 81.12 €.
    fnac_287 = (
        "OCEANE. 3. L'Initiateur s'engage irrévocablement à acquérir au prix "
        "unitaire de 36 € par action FNAC DARTY (dividende attac"
    )
    price, _ = _extract_first_price(fnac_287)
    assert price == Decimal("36"), "deferred to 02b: real FNAC DARTY offer is 81.12"

    # FNAC DARTY 226C0644 — same pattern, different wording.
    fnac_644 = (
        "cune OCEANE.    3.  L'Initiateur s'engage irrévocablement à acquérir "
        "au prix de 36 euros par action FNAC DARTY (dividende atta"
    )
    price, _ = _extract_first_price(fnac_644)
    assert price == Decimal("36"), "deferred to 02b: real FNAC DARTY offer is 81.12"
