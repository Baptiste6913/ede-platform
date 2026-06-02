"""P12b Step 0 — Euronext Growth identity cross-check pre-flight.

The 72 deals flagged ``home_venue_growth`` resolved to a Yahoo ticker via the
currency-strip heuristic, but Bloomberg's Growth ticker != the Yahoo symbol
(ALCLA.PA = Claranova, not Clasquin). The fix: cross-check the candidate
ticker's yfinance company name against the deal ``target_name``. A match
CONFIRMS the ticker; a mismatch REJECTS the collision.

This pre-flight: inventory the 72, resolve their candidate Yahoo tickers (from
the OpenFIGI cache), and run the cross-check on a 10-deal sample to size the
recoverable set and pick a threshold. No DB writes, no new dependency
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
SAMPLE_N = 10

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
    isin: str
    yahoo_ticker: str | None


async def _growth_deals() -> list[GrowthRow]:
    engine = get_engine()
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with sf() as session:
        rows = (
            await session.execute(
                select(Deal.id, Deal.target_name, Deal.ticker_target)
                .where(Deal.ticker_resolution_flag == "home_venue_growth")
                .order_by(Deal.id)
            )
        ).all()
    await dispose_engine()
    key = get_settings().openfigi_api_key.get_secret_value()
    resolver = OpenFIGIResolver(key, cache_path=CACHE_PATH, use_cache=True)
    out: list[GrowthRow] = []
    for did, name, isin in rows:
        res = resolver.resolve_isin_to_yahoo_ticker(isin) if isin else None
        out.append(
            GrowthRow(int(did), str(name), str(isin or ""), res.yahoo_ticker if res else None)
        )
    return out


def _yf_names(ticker: str) -> tuple[str, str]:
    try:
        info = yf.Ticker(ticker).info
        return str(info.get("shortName") or ""), str(info.get("longName") or "")
    except Exception:
        return "", ""


def main() -> None:
    rows = asyncio.run(_growth_deals())
    sample = rows[:SAMPLE_N]
    results = []
    for r in sample:
        short, long = _yf_names(r.yahoo_ticker) if r.yahoo_ticker else ("", "")
        best_name = short or long
        ratio, hit = _score(r.target_name, best_name) if best_name else (0.0, False)
        confirmed = bool(best_name) and (ratio >= 0.6 or hit)  # noqa: PLR2004
        results.append((r, short, long, ratio, hit, confirmed))

    n_conf = sum(1 for *_, c in results if c)
    n_named = sum(1 for _, s, lo, *_ in results if s or lo)
    rate = n_conf / len(results) if results else 0.0
    projected = round(rate * len(rows))

    lines: list[str] = []
    lines.append("# P12b Step 0 — Euronext Growth identity cross-check pre-flight\n")
    lines.append(
        f"{len(rows)} deals flagged `home_venue_growth`. Cross-check = fuzzy-match "
        "the candidate Yahoo ticker's company name (yfinance shortName/longName) "
        "against `target_name`; CONFIRM on match, REJECT collisions "
        "(ALCLA.PA=Claranova). difflib token-sort ratio + distinctive-token "
        "containment (token >=5 chars present), threshold ratio >= 0.6 OR hit.\n"
    )
    lines.append(f"## Sample ({len(sample)} deals)\n")
    lines.append("| Deal | target_name | ticker | yfinance name | ratio | tok-hit | verdict |")
    lines.append("|---|---|---|---|---:|:--:|:--:|")
    for r, short, long, ratio, hit, confirmed in results:
        nm = (short or long or "—")[:28]
        v = "✅ CONFIRM" if confirmed else ("❌ REJECT" if (short or long) else "· no-data")
        lines.append(
            f"| {r.deal_id} | {r.target_name[:22]} | {r.yahoo_ticker or '-'} | {nm} | "
            f"{ratio:.2f} | {'Y' if hit else 'n'} | {v} |"
        )
    lines.append("")
    lines.append("## Estimate\n")
    lines.append(f"- Sample CONFIRMED: **{n_conf}/{len(sample)}** ({rate * 100:.0f} %).")
    lines.append(f"- Sample with a yfinance name (resolvable): {n_named}/{len(sample)}.")
    lines.append(f"- Projected over {len(rows)} Growth deals: **~{projected}** recoverable.")
    lines.append("")
    lines.append("## Go/no-go\n")
    if projected >= 30:  # noqa: PLR2004
        lines.append(f"- **GO Step 1** — projected ~{projected} ≥ 30. Run the full cross-check.")
    else:
        lines.append(
            f"- **<30 projected (~{projected})** — fuzzy cross-check alone is thin; "
            "manual ISIN→Euronext-mnemonic curation likely needed. Re-discuss."
        )
    lines.append("")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[P12b-0] sample CONFIRMED {n_conf}/{len(sample)} | projected ~{projected}/{len(rows)}")
    print(f"[P12b-0] MD: {OUT_MD}")


if __name__ == "__main__":
    main()
