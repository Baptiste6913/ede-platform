# P9.1a — Pattern B diagnosis: mixed / share-exchange consideration

**Status:** diagnosis only — no fix in this commit. Validated against the
ProSiebenSat.1 and Commerzbank fixture PDFs in `tests/fixtures/p91a/`.

## TL;DR

The parser models consideration as a **single EUR scalar** (`offer_price`). For
offers paid in shares — with or without a cash leg — it captures only the cash
EUR amount, or, when there is no cash, falls through to the par-value `1.00`
(Cluster A). The share leg (exchange ratio + acquirer security) is lost, so
`offer_price` is understated or meaningless.

| deal | structure | stored | true value |
|---|---|--:|---|
| ProSiebenSat.1 (1059) | cash **+** shares | 4.48 | EUR 4.48 **+** 0.4 × P(MFE A) |
| Commerzbank (348) | shares only (no cash) | 1.00 (par value) | 0.485 × P(UniCredit) ≈ EUR 16–18 |

## Cases (PDF excerpts, first 10 pages)

**ProSiebenSat.1 (DE000PSM7770) — cash + shares**
> "…der ProSiebenSat.1 Media SE gegen Zahlung einer **Geldleistung in Höhe von
> EUR 4,48 und Gewährung von 0,4 Stückaktien A der MFE-MEDIAFOREUROPE N.V.** je
> einer Aktie der ProSiebenSat.1 Media SE"

- cash leg: **EUR 4.48**
- share leg: **0.4** class-A shares of **MFE-MEDIAFOREUROPE N.V.** per ProSieben share
- target ISIN: DE000PSM7770
- stored `offer_price = 4.48` → cash leg only; the 0.4-share leg is dropped.
  Total economic value = `4.48 + 0.4 × P(MFE A)`.

**Commerzbank (DE000CBK1001) — pure share swap (no cash)**
> "…der COMMERZBANK Aktiengesellschaft gegen **Gewährung einer Gegenleistung von
> 0,485 Aktien der UniCredit S.p.A.** für jeweils eine Aktie der COMMERZBANK
> Aktiengesellschaft"

- share leg only: **0.485** shares of **UniCredit S.p.A.** per Commerzbank share, **no cash**
- Commerzbank ISIN: DE000CBK1001 (tendered: DE000A41YE64)
- stored `offer_price = 1.00` → par value (Cluster A), because there is no EUR
  offer amount to find. Real value ≈ `0.485 × P(UniCredit)` ≈ EUR 16–18, matching
  the Step-0 expectation.

## Code path

- `_extract_price` — `src/ingestion/bafin/parser.py:192-202` — single EUR scalar,
  no concept of a share-consideration leg.
- `ParsedBafinMetadata` — `parser.py:104-117` — only `offer_price` / `currency`;
  no fields for exchange ratio or acquirer security.
- Model — `src/core/models.py:111-113`: `Deal.offer_price` is a lone `Numeric`;
  `Deal.payment_cash_share` (`Numeric(5,4)`) exists but is **never populated**;
  there is no field for the exchange ratio or the acquirer's security/ISIN.

## Detection signals in the PDF

`Gewährung von <ratio> (Stück)aktien [A] der <Acquirer> je … Aktie`,
`Gegenleistung von <ratio> Aktien der <Acquirer>`, `Umtauschverhältnis`,
`Aktientausch`.
Note: ProSieben and Commerzbank both phrase it as
*"Gewährung … Aktien"* / *"Gegenleistung von … Aktien"* — **not** the literal
word *"Umtauschverhältnis"*. The regex must key on
`Gewährung|Gegenleistung … <ratio> Aktien der <Acquirer>`, not only on
`Umtauschverhältnis`.

## Fix hypothesis (not implemented)

Parse consideration as a **structure**:
`{cash_eur, share_ratio, acquirer_name / ISIN}`. Compute the economic offer
value = `cash_eur + share_ratio × acquirer_price` — the acquirer quote ties this
into the P9.1b external-pricing work. Persist the cash/share split (reuse
`payment_cash_share`; add acquirer security + ratio fields → likely migration
0014). When an offer is share-based, never store the bare par-value scalar;
record it as a mixed/share offer instead.
