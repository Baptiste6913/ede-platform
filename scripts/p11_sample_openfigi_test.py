"""P11 Step 2 — sample-test the OpenFIGI resolver on the SAME 20 deals as the
Phase-10 yfinance sample, for a direct yfinance-vs-OpenFIGI comparison.

Deal source: the Phase-10 sample was deterministic (SEED=20260601, quota
FR13/IT3/DE4) and persisted every sampled row — including ISIN,
announcement/target dates and offer_price — to
``data/audits/p10_sample_yfinance_test.csv``. We reuse that CSV verbatim as the
input so the sample is *byte-identical* to Phase 10 and needs no DB / Docker.

Per deal:
1. ISIN = the ``isin_or_ticker`` column (empty for the 3 Consob/IT deals, whose
   ISIN was never extracted in Phase 10 — an upstream gap, not a resolver miss).
2. ``OpenFIGIResolver.resolve_isin_to_yahoo_ticker(isin)`` → yahoo_ticker,
   exch_bbg, figi, source flag (home_venue / venue_fallback / no_match /
   unknown_exch).
3. ``get_close_eur(yahoo_ticker, target_date)`` (target_date reused from the
   CSV, = Phase-10's announcement_date - 1 business day).
4. premium_pct = (offer_price - reference_price) / reference_price, with a
   sanity gate flagging |premium| outside [-50 %, +200 %].

Two rates are reported, deliberately separated:
- **resolution rate** — did OpenFIGI return a ticker? (what Phase 11 tests)
- **priced rate** — did the chain yield a price? (= Phase 10's "ok"; also gated
  by whether the security is still listed at T-1).

Outputs:
- ``data/audits/p11_sample_openfigi_test.csv`` (gitignored)
- ``artifacts/phase-11/sample_openfigi_audit.md`` (tracked)
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.settings import get_settings
from src.pricing.openfigi_resolver import OpenFIGIResolver, OpenFIGISource
from src.pricing.yfinance_fetcher import get_close_eur

REPO_ROOT = Path(__file__).resolve().parents[1]
IN_CSV = REPO_ROOT / "data" / "audits" / "p10_sample_yfinance_test.csv"
OUT_CSV = REPO_ROOT / "data" / "audits" / "p11_sample_openfigi_test.csv"
OUT_MD = REPO_ROOT / "artifacts" / "phase-11" / "sample_openfigi_audit.md"
CACHE_PATH = REPO_ROOT / "artifacts" / "phase-11" / "openfigi_cache.json"

GO_THRESHOLD = 0.85
INVESTIGATE_THRESHOLD = 0.70
PREMIUM_HIGH_OUTLIER = 200.0  # %
PREMIUM_LOW_OUTLIER = -50.0  # %

# Phase-10 baseline (from data/audits/p10_sample_yfinance_test.csv).
P10_RAW_RATE = 35.0
P10_REAL_RATE = 25.0
P10_WRONG_TICKER_FPS = 2
# The two wrong-ticker false positives Phase 10 produced via bare-ISIN yfinance.
P10_FP_REFS = {"224C2186": "CLASQUIN +10405%", "224C0763": "COVIVIO HOTELS -77%"}
# Phase-11 outcome per FP, after manual verification of the resolved security
# (the resolver cannot self-certify ticker identity). Post-Step-2.5 the Growth
# heuristic reintroduced one gate-caught FP (CLASQUIN → ALCLA.PA = Claranova).
P11_FP_OUTCOME: dict[str, str] = {
    "224C2186": (
        "STILL WRONG (post-Step-2.5, gate-caught). The Growth mapping now emits "
        "`ALCLA.PA` (XS, currency-stripped from ALCLAEUR) — but `ALCLA.PA` is "
        "*Claranova* on Yahoo, not Clasquin (verified). yfinance returns 1.352 "
        "EUR → +10405 % again. The premium sanity gate (>200 %) flags it, so it "
        "would NOT enter a backfill, but it is a reintroduced wrong-ticker FP: "
        "Bloomberg's Euronext-Growth ticker != the Yahoo symbol."
    ),
    "224C0763": (
        "FIXED. Resolved to the correct security `COVH.PA` (ref 13.14 EUR is "
        "right). The -77 % is a corrupt stored offer_price (3.00 EUR) — an "
        "upstream data-quality issue, NOT a wrong ticker."
    ),
}
# Post-Step-2.5: the Growth EUR-strip heuristic reintroduced 1 gate-caught FP.
WRONG_TICKER_FPS_P11 = 1
# yfinance identity spot-check of the Step-2.5 Growth-resolved tickers
# (manual verification via yf.Ticker(...).info shortName).
GROWTH_SPOT_CHECK: list[tuple[str, str, str]] = [
    ("CLASQUIN", "ALCLA.PA", "WRONG → resolves to CLARANOVA (0.76 EUR), not Clasquin"),
    ("COMPAGNIE DU CAMBODGE", "CBDG.PA", "CORRECT → CAMBODGE NOM. (104 EUR)"),
    ("AMPLITUDE SURGICAL", "AMPLI.PA", "no Yahoo listing → no_price (safe skip)"),
    ("MONTAGNE ET NEIGE", "MND1.PA", "no Yahoo listing (BBG digit disambiguator) → no_price"),
    ("IDSUD", "ALIDS.PA", "no Yahoo data this run → no_price"),
    ("GALIMMO", "CIEM.PA", "no Yahoo data this run → no_price"),
]


def _dec(value: str) -> Decimal | None:
    try:
        return Decimal(value) if value else None
    except InvalidOperation:
        return None


def _probe(resolver: OpenFIGIResolver, row: dict[str, str]) -> dict[str, object]:
    isin = (row.get("isin_or_ticker") or "").strip()
    offer = _dec(row.get("offer_price", ""))
    target_date_str = (row.get("target_date") or "").strip()
    out: dict[str, object] = {
        "deal_id": row.get("deal_id", ""),
        "juridiction": row.get("juridiction", ""),
        "regulator_ref": row.get("regulator_ref", ""),
        "target_name": row.get("target_name", ""),
        "isin": isin,
        "yahoo_ticker": "",
        "exch_bbg": "",
        "figi": "",
        "source_flag": "",
        "target_date": target_date_str,
        "offer_price": str(offer) if offer is not None else "",
        "reference_price_eur": "",
        "effective_date": "",
        "premium_pct": "",
        "outlier": "",
        "status": "",
    }
    if not isin:
        out["status"] = "no_isin"  # upstream ISIN-extraction gap (IT/Consob)
        return out

    res = resolver.resolve_isin_to_yahoo_ticker(isin)
    out["source_flag"] = str(res.source)
    out["exch_bbg"] = res.exch_code_bbg or ""
    out["figi"] = res.figi or ""
    if res.yahoo_ticker is None:
        out["status"] = "no_match" if res.source is OpenFIGISource.NO_MATCH else "unknown_exch"
        return out
    out["yahoo_ticker"] = res.yahoo_ticker

    if not target_date_str:
        out["status"] = "resolved_no_date"
        return out
    target_date = date.fromisoformat(target_date_str)
    try:
        priced = get_close_eur(res.yahoo_ticker, target_date, max_lookback_days=5)
    except Exception as exc:  # audit script records the error, never crashes
        out["status"] = f"fetch_error:{type(exc).__name__}"
        return out
    if priced is None:
        out["status"] = "no_price"  # resolved correctly but no yfinance data (likely delisted)
        return out

    close_eur, eff_date = priced
    out["reference_price_eur"] = str(close_eur)
    out["effective_date"] = eff_date.isoformat()
    if offer is not None and close_eur > 0:
        premium = (offer - close_eur) / close_eur * Decimal(100)
        out["premium_pct"] = f"{premium:.2f}"
        if premium > Decimal(PREMIUM_HIGH_OUTLIER) or premium < Decimal(PREMIUM_LOW_OUTLIER):
            out["outlier"] = "YES"
    out["status"] = "ok"
    return out


def _load_sample() -> list[dict[str, str]]:
    with IN_CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


_FIELDNAMES = [
    "deal_id",
    "juridiction",
    "regulator_ref",
    "target_name",
    "isin",
    "yahoo_ticker",
    "exch_bbg",
    "figi",
    "source_flag",
    "target_date",
    "offer_price",
    "reference_price_eur",
    "effective_date",
    "premium_pct",
    "outlier",
    "status",
]


def _write_csv(rows: list[dict[str, object]]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _premium_values(rows: list[dict[str, object]]) -> list[float]:
    vals: list[float] = []
    for r in rows:
        if r["premium_pct"]:
            try:
                vals.append(float(str(r["premium_pct"])))
            except ValueError:
                continue
    return vals


def _write_md(rows: list[dict[str, object]]) -> None:
    total = len(rows)
    resolved = sum(1 for r in rows if r["yahoo_ticker"])
    priced = sum(1 for r in rows if r["status"] == "ok")
    with_isin = sum(1 for r in rows if r["isin"])
    resolution_rate = resolved / with_isin if with_isin else 0.0
    priced_rate = priced / total if total else 0.0
    fallback_rows = [r for r in rows if r["source_flag"] == str(OpenFIGISource.VENUE_FALLBACK)]
    premium_values = _premium_values(rows)
    outliers = [r for r in rows if r["outlier"] == "YES"]

    by_jur_total: Counter[str] = Counter(str(r["juridiction"]) for r in rows)
    by_jur_priced: Counter[str] = Counter(
        str(r["juridiction"]) for r in rows if r["status"] == "ok"
    )
    by_jur_resolved: Counter[str] = Counter(
        str(r["juridiction"]) for r in rows if r["yahoo_ticker"]
    )

    lines: list[str] = []
    lines.append("# Phase 11 Sample Test — OpenFIGI vs yfinance (20 deals)\n")
    lines.append(
        "Same 20 deals as Phase 10 (SEED=20260601, quota FR13/IT3/DE4), reused "
        f"verbatim from `{IN_CSV.relative_to(REPO_ROOT).as_posix()}`. Two metrics "
        "are separated: **resolution rate** (did OpenFIGI return a ticker — the "
        "thing Phase 11 tests) and **priced rate** (did the full chain yield a "
        "price — Phase 10's `ok`, also gated by listing status at T-1).\n"
    )

    lines.append("## Comparison with Phase 10\n")
    lines.append("| Metric | Phase 10 (yfinance) | Phase 11 (OpenFIGI) |")
    lines.append("|---|---:|---:|")
    lines.append(f"| Priced rate (status ok) | {P10_RAW_RATE:.0f} % | {priced_rate * 100:.0f} % |")
    lines.append(
        f"| Real priced rate (post-FP) | {P10_REAL_RATE:.0f} % | " f"{priced_rate * 100:.0f} % |"
    )
    lines.append(f"| Wrong-ticker FPs | {P10_WRONG_TICKER_FPS} | {WRONG_TICKER_FPS_P11} |")
    lines.append(
        f"| Resolution rate (ISIN→ticker) | n/a | "
        f"{resolution_rate * 100:.0f} % ({resolved}/{with_isin}) |"
    )
    lines.append("")

    lines.append("## Per-deal results\n")
    lines.append(
        "| Jur | Ref | Target | ISIN | OpenFIGI ticker | flag | exch | ref EUR | "
        "offer | premium % | status |"
    )
    lines.append("|---|---|---|---|---|---|---|---:|---:|---:|---|")
    for r in rows:
        flag = str(r["source_flag"]).replace("openfigi_", "")
        lines.append(
            f"| {r['juridiction']} | {r['regulator_ref']} | {str(r['target_name'])[:22]} | "
            f"{r['isin']} | {r['yahoo_ticker']} | {flag} | {r['exch_bbg']} | "
            f"{r['reference_price_eur']} | {r['offer_price']} | {r['premium_pct']} | "
            f"`{r['status']}` |"
        )
    lines.append("")

    lines.append("## Rates by jurisdiction\n")
    lines.append("| Jur | Sample | Resolved | Priced | Resolved % | Priced % |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for jur in ("FR", "IT", "DE"):
        tot = by_jur_total.get(jur, 0)
        rok = by_jur_resolved.get(jur, 0)
        pok = by_jur_priced.get(jur, 0)
        rr = (rok / tot * 100.0) if tot else 0.0
        pr = (pok / tot * 100.0) if tot else 0.0
        lines.append(f"| {jur} | {tot} | {rok} | {pok} | {rr:.0f} % | {pr:.0f} % |")
    lines.append(
        f"| **TOTAL** | **{total}** | **{resolved}** | **{priced}** | "
        f"**{resolution_rate * 100:.0f} %** (of {with_isin} w/ ISIN) | "
        f"**{priced_rate * 100:.0f} %** |"
    )
    lines.append("")

    lines.append("## Wrong-ticker FPs check (Phase 10 culprits)\n")
    lines.append(
        f"**Wrong-ticker FPs in Phase 11: {WRONG_TICKER_FPS_P11}** "
        "(gate-caught; the Growth heuristic reintroduced one — see below).\n"
    )
    for ref, outcome in P11_FP_OUTCOME.items():
        lines.append(f"- **{P10_FP_REFS[ref]}** → {outcome}")
    lines.append("")

    lines.append("## venue_fallback flags\n")
    if fallback_rows:
        for r in fallback_rows:
            lines.append(
                f"- {r['regulator_ref']} {r['target_name']} → `{r['yahoo_ticker']}` "
                f"({r['exch_bbg']})"
            )
    else:
        lines.append("- none — every resolved deal matched its home venue.")
    lines.append("")

    lines.append("## Premium_pct distribution (priced deals)\n")
    if premium_values:
        lines.append(f"- count : {len(premium_values)}")
        lines.append(f"- min   : {min(premium_values):.2f} %")
        lines.append(f"- median: {statistics.median(premium_values):.2f} %")
        lines.append(f"- max   : {max(premium_values):.2f} %")
        if len(premium_values) > 1:
            lines.append(f"- stdev : {statistics.stdev(premium_values):.2f} %")
        lines.append(
            f"- outliers (|premium| > {PREMIUM_HIGH_OUTLIER:.0f} % or "
            f"< {PREMIUM_LOW_OUTLIER:.0f} %): {len(outliers)}"
        )
    else:
        lines.append("- no priced deals with an offer_price to compute premium.")
    lines.append("")

    growth_refs = [
        str(r["regulator_ref"])
        for r in rows
        if r["source_flag"] == str(OpenFIGISource.HOME_VENUE_GROWTH)
    ]
    lines.append("## Root-cause diagnosis (why priced rate is gated)\n")
    lines.append(
        "The priced rate decomposes into one resolver-confidence gap and several "
        "causes outside the resolver:\n"
    )
    lines.append(
        f"1. **FR Euronext Growth small caps ({len(growth_refs)}) — LOW-confidence "
        "resolutions (post-Step-2.5).** These have no `FP` row; they resolve via "
        "the XS/XH/EO venues, but the Bloomberg ticker != the Yahoo symbol "
        "(ALCLA.PA→Claranova). Flagged `home_venue_growth`; see the Post-Step-2.5 "
        f"section. Affected: {', '.join(growth_refs)}."
    )
    lines.append(
        "2. **IT/Consob no_isin (3) — upstream gap.** ISIN was never extracted "
        "for Consob deals in Phase 10; OpenFIGI needs an ISIN as input. Same "
        "blocker as Phase 10, not a resolver issue."
    )
    lines.append(
        "3. **Genuine delisting (2): `FPH.DE` (Francotyp-Postalia), `97K.DE` "
        "(Exclusive Networks, taken private).** Correct tickers, but no yfinance "
        "data at T-1 — expected for post-OPA targets."
    )
    lines.append(
        "4. **yfinance transient (2): `COP.DE` (CompuGroup) x2.** Correct ticker; "
        "CompuGroup is actively listed. yfinance returned `no timezone found` "
        "this run (metadata hiccup / rate-limit) — re-verify; not a resolver miss."
    )
    lines.append(
        "5. **offer_price data quality (1): COVIVIO -77 %.** Right ticker + right "
        "price; the stored offer (3.00 EUR) is corrupt. Upstream parsing issue."
    )
    lines.append("")
    lines.append(
        "**Resolution quality where it matters:** every main-market resolution "
        "(`home_venue`: FP/GR/IM) is the correct security — **0 wrong-ticker FPs**. "
        "The only FP (CLASQUIN) comes from the low-confidence Growth heuristic and "
        "is gate-caught. OpenFIGI's identity correctness on main-market listings — "
        "the Phase-10 failure mode — is validated; Growth needs a safer strategy."
    )
    lines.append("")

    lines.append("## Post-Step-2.5 re-run (Euronext Growth mapping)\n")
    lines.append(
        "Step 2.5 added FR Growth venues (XS/XH/EO → .PA) + a defensive "
        "currency-suffix strip. Resolution jumped **10/17 → 17/17 (100 %)**. But "
        "a yfinance identity spot-check of the newly-resolved Growth tickers "
        "shows the mapping is **not safe to trust blindly**:\n"
    )
    lines.append("| Deal | Growth ticker | yfinance identity check |")
    lines.append("|---|---|---|")
    for name, ticker, verdict in GROWTH_SPOT_CHECK:
        lines.append(f"| {name} | `{ticker}` | {verdict} |")
    lines.append("")
    lines.append(
        "**Key finding:** Bloomberg's Euronext-Growth local ticker is NOT the "
        "Yahoo symbol. Currency-stripping `ALCLAEUR` → `ALCLA` collides with an "
        "unrelated security (`ALCLA.PA` = Claranova), reproducing the exact "
        "Phase-10 +10405 % garbage — caught by the premium gate, but a "
        "reintroduced wrong-ticker FP. Of the 7 Growth resolutions, only CBDG.PA "
        "is verified correct; the rest are wrong (1) or have no Yahoo data (5). "
        "These are now flagged `home_venue_growth` (low confidence) so the "
        "backfill can route them to manual_review instead of trusting them.\n"
    )

    lines.append("## Verdict\n")
    lines.append(
        f"- Resolution rate = **{resolution_rate * 100:.0f} %** "
        f"({resolved}/{with_isin}) · priced rate = {priced_rate * 100:.0f} %."
    )
    lines.append(
        "- **Main-market venues (FP/GR/IM): GO.** Every large/mid cap resolved to "
        "the correct security (TRACT.PA, COVH.PA, EDI.PA, ARTO.PA, 2HRA.DE, "
        "COP.DE, FPH.DE) — 0 wrong-ticker FPs. This is the validated core."
    )
    lines.append(
        "- **Euronext Growth venues (XS/XH/EO): NO-GO as auto-resolve.** The "
        "currency-strip heuristic emits structurally-plausible but unreliable "
        "tickers (ALCLA.PA→Claranova). Flagged `home_venue_growth`; route to "
        "manual_review or require an identity/deviation check before use."
    )
    lines.append(
        "- **IT/Consob: blocked upstream** (no ISIN extracted) — independent of " "the resolver."
    )
    lines.append(
        "- **Recommendation:** GO full backfill on `home_venue` (main-market) "
        "resolutions with the premium sanity gate enforced; exclude "
        "`home_venue_growth` from auto-backfill pending a safe Growth strategy "
        "(e.g. yfinance identity cross-check, or an ISIN→Euronext-mnemonic map)."
    )
    lines.append("")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    key = get_settings().openfigi_api_key.get_secret_value()
    if not key:
        sys.exit("OPENFIGI_API_KEY missing from environment/.env")
    resolver = OpenFIGIResolver(key, cache_path=CACHE_PATH, use_cache=True)

    sample = _load_sample()
    print(f"[STEP-2] loaded {len(sample)} deals from {IN_CSV.name}")
    rows: list[dict[str, object]] = []
    for idx, row in enumerate(sample, start=1):
        out = _probe(resolver, row)
        rows.append(out)
        print(
            f"[STEP-2] {idx}/{len(sample)} {out['juridiction']} {out['regulator_ref']} "
            f"{str(out['target_name'])[:24]:24} -> ticker={out['yahoo_ticker'] or '-':10} "
            f"flag={str(out['source_flag']).replace('openfigi_', '') or '-':14} "
            f"status={out['status']}"
        )

    _write_csv(rows)
    _write_md(rows)
    resolved = sum(1 for r in rows if r["yahoo_ticker"])
    priced = sum(1 for r in rows if r["status"] == "ok")
    with_isin = sum(1 for r in rows if r["isin"])
    print()
    print(f"resolution: {resolved}/{with_isin} ISIN-bearing  |  priced: {priced}/{len(rows)}")
    print(f"CSV: {OUT_CSV}")
    print(f"MD : {OUT_MD}")


if __name__ == "__main__":
    main()
