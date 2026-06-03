"""P12b Step 0 — Euronext Growth identity cross-check pre-flight.

The 72 deals flagged ``home_venue_growth`` resolved to a Yahoo ticker via the
currency-strip heuristic, but Bloomberg's Growth ticker != the Yahoo symbol
(ALCLA.PA = Claranova, not Clasquin). The fix: cross-check the candidate
ticker's yfinance company name against the deal ``target_name``. A match
CONFIRMS the ticker; a mismatch REJECTS the collision.

This pre-flight: inventory all 72, resolve their candidate Yahoo tickers (from
the OpenFIGI cache), aggregate to distinct (target, jurisdiction) clusters, and
run the identity cross-check on each. No DB writes, no new dependency
(``difflib`` instead of rapidfuzz).

Output: ``artifacts/phase-12b/growth_crosscheck_preflight.md``.
"""

from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.db import dispose_engine, get_engine
from src.core.models import Deal
from src.core.settings import get_settings
from src.pricing.openfigi_resolver import CACHE_PATH, OpenFIGIResolver

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = REPO_ROOT / "artifacts" / "phase-12b" / "growth_crosscheck_preflight.md"

# Legal forms / generic tokens stripped before fuzzy comparison.
_STOP = {
    "sa",
    "se",
    "spa",
    "ag",
    "nv",
    "plc",
    "ltd",
    "gmbh",
    "kgaa",
    "scs",
    "sca",
    "srl",
    "sas",
    "inc",
    "co",
    "the",
    "group",
    "groupe",
    "holding",
    "holdings",
    "company",
    "nom",
    "act",
    "regroupement",
    "et",
    "de",
    "du",
    "des",
    "la",
    "le",
}


def _norm(s: str) -> list[str]:
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return [t for t in s.split() if t and t not in _STOP]


def _score(target: str, name: str) -> tuple[float, bool]:
    """Return (token_sort_ratio, distinctive_token_hit)."""
    tt, nt = _norm(target), _norm(name)
    if not tt or not nt:
        return 0.0, False
    ratio = SequenceMatcher(None, " ".join(sorted(tt)), " ".join(sorted(nt))).ratio()
    # Distinctive-token containment: any target token >=5 chars present in name.
    nset = set(nt)
    hit = any(len(t) >= 5 and t in nset for t in tt)  # noqa: PLR2004
    return ratio, hit


@dataclass
class GrowthRow:
    deal_id: int
    target_name: str
    jurisdiction: str
    isin: str
    yahoo_ticker: str | None


async def _growth_deals() -> list[GrowthRow]:
    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        rows = (
            await session.execute(
                select(Deal.id, Deal.target_name, Deal.juridiction, Deal.ticker_target)
                .where(Deal.ticker_resolution_flag == "home_venue_growth")
                .order_by(Deal.id)
            )
        ).all()
    await dispose_engine()
    key = get_settings().openfigi_api_key.get_secret_value()
    resolver = OpenFIGIResolver(key, cache_path=CACHE_PATH, use_cache=True)
    out: list[GrowthRow] = []
    for did, name, jur, isin in rows:
        res = resolver.resolve_isin_to_yahoo_ticker(isin) if isin else None
        out.append(
            GrowthRow(
                int(did), str(name), str(jur), str(isin or ""), res.yahoo_ticker if res else None
            )
        )
    return out


def _yf_names(ticker: str) -> tuple[str, str]:
    try:
        info = yf.Ticker(ticker).info
        return str(info.get("shortName") or ""), str(info.get("longName") or "")
    except Exception:
        return "", ""


@dataclass
class ClusterVerdict:
    target_name: str
    jurisdiction: str
    ticker: str | None
    yf_name: str
    ratio: float
    verdict: str  # CONFIRM | REJECT | no_data | no_ticker


def _classify(
    target: str, ticker: str | None, name_cache: dict[str, tuple[str, str]]
) -> ClusterVerdict:
    if not ticker:
        return ClusterVerdict(target, "", None, "", 0.0, "no_ticker")
    if ticker not in name_cache:
        name_cache[ticker] = _yf_names(ticker)
    short, long = name_cache[ticker]
    best = short or long
    if not best:
        return ClusterVerdict(target, "", ticker, "", 0.0, "no_data")
    ratio, hit = _score(target, best)
    verdict = "CONFIRM" if (ratio >= 0.6 or hit) else "REJECT"  # noqa: PLR2004
    return ClusterVerdict(target, "", ticker, best, ratio, verdict)


def main() -> None:
    rows = asyncio.run(_growth_deals())
    # Aggregate to distinct (target, jurisdiction) clusters — premium is per cluster.
    by_cluster: dict[tuple[str, str], GrowthRow] = {}
    for r in rows:
        by_cluster.setdefault((r.target_name, r.jurisdiction), r)

    name_cache: dict[str, tuple[str, str]] = {}
    verdicts: list[ClusterVerdict] = []
    for (target, jur), r in by_cluster.items():
        cv = _classify(target, r.yahoo_ticker, name_cache)
        cv.jurisdiction = jur
        verdicts.append(cv)

    n_clusters = len(verdicts)
    counts = {
        k: sum(1 for v in verdicts if v.verdict == k)
        for k in ("CONFIRM", "REJECT", "no_data", "no_ticker")
    }
    confirmed = counts["CONFIRM"]

    lines: list[str] = []
    lines.append("# P12b Step 0 — Euronext Growth identity cross-check (FULL inventory)\n")
    lines.append(
        f"All {len(rows)} `home_venue_growth` deals → **{n_clusters} distinct "
        "(target, jurisdiction) clusters** (premium is per cluster). Cross-check = "
        "fuzzy-match the candidate Yahoo ticker's yfinance company name vs "
        "`target_name` (difflib token-sort ratio + distinctive-token, threshold "
        ">= 0.6 OR token hit). CONFIRM = identity matches; REJECT = collision "
        "(e.g. ALCLA.PA=Claranova); no_data = yfinance has no name (delisted "
        "micro-cap, also un-priceable).\n"
    )
    lines.append("## Cluster verdicts\n")
    lines.append("| Target | Jur | ticker | yfinance name | ratio | verdict |")
    lines.append("|---|---|---|---|---:|:--:|")
    for v in sorted(verdicts, key=lambda x: (x.verdict, x.target_name)):
        mark = {"CONFIRM": "✅", "REJECT": "❌", "no_data": "·", "no_ticker": "·"}[v.verdict]
        lines.append(
            f"| {v.target_name[:24]} | {v.jurisdiction} | {v.ticker or '-'} | "
            f"{(v.yf_name or '—')[:24]} | {v.ratio:.2f} | {mark} {v.verdict} |"
        )
    lines.append("")
    lines.append("## Counts (cluster level)\n")
    lines.append(f"- Distinct Growth clusters: **{n_clusters}**")
    lines.append(f"- ✅ CONFIRM (identity matches, recoverable): **{confirmed}**")
    lines.append(f"- ❌ REJECT (collision, correctly excluded): {counts['REJECT']}")
    lines.append(f"- · no_data (delisted, un-priceable regardless): {counts['no_data']}")
    lines.append(f"- · no_ticker: {counts['no_ticker']}")
    lines.append("")
    lines.append(
        "**Note:** CONFIRM is the *identity* ceiling. Usable premium also needs a "
        "T-1 yfinance price + passing the premium gate — a further haircut on the "
        f"{confirmed} confirmed.\n"
    )
    lines.append("## Go/no-go\n")
    if confirmed >= 15:  # noqa: PLR2004
        lines.append(
            f"- **GO Step 1** — {confirmed} confirmed clusters materially lift "
            f"coverage (25 → up to ~{25 + confirmed})."
        )
    else:
        lines.append(
            f"- **Thin ({confirmed} confirmed clusters).** Growth recovery is "
            "data-limited (no_data dominates); the ~80-100 target is not reachable "
            "from Growth. Re-scope: offer_price fixes only, or accept the ceiling."
        )
    lines.append("")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(
        f"[P12b-0] clusters={n_clusters} CONFIRM={confirmed} REJECT={counts['REJECT']} "
        f"no_data={counts['no_data']} no_ticker={counts['no_ticker']}"
    )
    print(f"[P12b-0] MD: {OUT_MD}")


if __name__ == "__main__":
    main()
