"""P14 Step 3 — generate actionable decisions for the scored fresh pool.

For each tradable candidate (fresh, completion_label NULL, score >= 3*, home_venue,
offer_price present) it:

1. computes the **takeover premium** from yfinance: reference price at
   announcement - 1 business day vs offer_price; persists premium_pct +
   reference_price_at_announcement; applies the sanity gate [-50%, +200%]
   (out-of-bounds => premium_out_of_bounds flag, excluded);
2. fetches the **current** price (yfinance, latest close) as the decision
   reference and runs the decision engine (entry/stop/TP/sizing/spread) -- no IBKR;
3. emits the decision (MD + index via MarkdownDecisionSink, Discord embed
   best-effort), independent of any paper execution.

Run:
    $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
    .venv/Scripts/python.exe scripts/p14_decide_fresh.py            # DRY-RUN
    .venv/Scripts/python.exe scripts/p14_decide_fresh.py --apply

Output: artifacts/phase-14/decisions_generated.md (tracked).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal, Score
from src.core.settings import get_settings
from src.output.decision_md import MarkdownDecisionSink
from src.pricing.yfinance_fetcher import get_close_eur
from src.trading.decision_engine import DealCandidate, DecisionEngine
from src.trading.discord_alerts import DiscordAlerts
from src.trading.ibkr_client import PriceSnapshot

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = REPO_ROOT / "artifacts" / "phase-14" / "decisions_generated.md"
SINCE = date(2025, 12, 3)
PREMIUM_LOW_PCT, PREMIUM_HIGH_PCT = -50.0, 200.0
RAMPUP_DONE = 5  # so generated decisions are not flagged requires_approval here
# Deals whose announcement predates this need a manual liveness check.
VIVACITE_CUTOFF = date(2026, 2, 1)


def _prev_business_day(d: date) -> date:
    c = d - timedelta(days=1)
    while c.weekday() >= 5:  # noqa: PLR2004 — Sat/Sun
        c -= timedelta(days=1)
    return c


async def _decide_one(
    deal: Deal,
    score: Score,
    *,
    decision_engine: DecisionEngine,
    settings: Any,
    today: date,
    sink: MarkdownDecisionSink,
    discord: DiscordAlerts,
    dry_run: bool,
) -> dict[str, Any]:
    """Produce (and emit) one decision, or an exclusion row. Mutates `deal`."""
    offer = float(deal.offer_price)
    ticker = deal.trading_ticker_yf or ""
    row: dict[str, Any] = {
        "jur": deal.juridiction,
        "target": deal.target_name,
        "ref": deal.regulator_ref,
        "ticker": deal.trading_ticker_yf,
        "stars": score.score_stars,
        "offer": offer,
        "vivacite": deal.announcement_date < VIVACITE_CUTOFF,
    }

    # 1. Takeover premium (T-1) + sanity gate.
    priced_t1 = get_close_eur(
        ticker, _prev_business_day(deal.announcement_date), max_lookback_days=7
    )
    if priced_t1 is None:
        row["status"] = "excluded: no T-1 price"
        return row
    ref_t1 = float(priced_t1[0])
    premium_pct = (offer - ref_t1) / ref_t1 if ref_t1 > 0 else float("nan")
    row["ref_t1"] = ref_t1
    row["premium_pct"] = premium_pct * 100.0
    if not (PREMIUM_LOW_PCT <= premium_pct * 100.0 <= PREMIUM_HIGH_PCT):
        row["status"] = f"excluded: premium_out_of_bounds ({premium_pct * 100:.1f}%)"
        if not dry_run:
            deal.ticker_resolution_flag = "premium_out_of_bounds"
            deal.premium_pct = None
        return row
    if not dry_run:
        deal.premium_pct = Decimal(str(round(premium_pct, 4)))
        deal.reference_price_at_announcement = Decimal(str(round(ref_t1, 4)))
        deal.reference_price_source = "openfigi+yfinance"

    # 2. Current price (decision reference) + decision engine.
    priced_now = get_close_eur(ticker, today, max_lookback_days=7)
    if priced_now is None:
        row["status"] = "excluded: no current price (likely delisted/closed)"
        return row
    ref_now = float(priced_now[0])
    row["ref_now"] = ref_now
    snapshot = PriceSnapshot(
        bid=None,
        ask=None,
        last=ref_now,
        close=ref_now,
        market_data_type=0,
        price_source="yfinance_close",
    )
    cand = DealCandidate(
        deal_id=deal.id,
        target_name=deal.target_name,
        acquirer_name=deal.acquirer_name,
        juridiction=deal.juridiction,
        offer_price=offer,
        p_completion=float(score.p_completion),
        score_stars=int(score.score_stars),
        symbol=deal.ibkr_ticker,
        exchange=deal.ibkr_exchange,
        isin=deal.ticker_target,
        yahoo_ticker=deal.trading_ticker_yf,
    )
    req = decision_engine.evaluate(cand, snapshot, settings.trading_capital_base, 0, RAMPUP_DONE)
    if req is None:
        row["status"] = "filtered by engine (thin spread / no edge / sizing)"
        return row

    row.update(
        status="DECISION",
        entry=req.limit_price,
        stop=req.stop_loss_price,
        tp=req.take_profit_price,
        spread_pct=req.expected_return_pct * 100.0,
        qty=req.quantity,
    )
    if not dry_run:
        await sink.emit(req, deal)
        try:
            await discord.decision_alert(req, deal)
        except Exception as exc:
            print(f"[P14-decide] discord failed for {deal.target_name}: {exc}")
    return row


async def _process(*, dry_run: bool) -> None:
    settings = get_settings()
    engine_db = create_async_engine(settings.database_url, future=True)
    sm = async_sessionmaker(engine_db, expire_on_commit=False)
    decision_engine = DecisionEngine.from_settings(settings)
    sink = MarkdownDecisionSink()
    discord = DiscordAlerts.from_settings(settings)
    today = date.today()
    rows: list[dict[str, Any]] = []

    async with sm() as session:
        candidates = list(
            (
                await session.execute(
                    select(Deal, Score)
                    .join(Score, Score.deal_id == Deal.id)
                    .where(
                        Deal.juridiction.in_(["FR", "DE"]),
                        Deal.announcement_date >= SINCE,
                        Deal.completion_label.is_(None),
                        Deal.ticker_resolution_flag == "home_venue",
                        Deal.offer_price.is_not(None),
                        Score.score_stars >= 3,  # noqa: PLR2004
                    )
                    .order_by(Score.score_stars.desc())
                )
            ).all()
        )
        print(f"[P14-decide] {len(candidates)} tradable candidates")

        for deal, score in candidates:
            rows.append(
                await _decide_one(
                    deal,
                    score,
                    decision_engine=decision_engine,
                    settings=settings,
                    today=today,
                    sink=sink,
                    discord=discord,
                    dry_run=dry_run,
                )
            )

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine_db.dispose()
    _write_md(rows, dry_run=dry_run)
    decisions = [r for r in rows if r["status"] == "DECISION"]
    print(f"[P14-decide] mode={'DRY-RUN' if dry_run else 'APPLY'} decisions={len(decisions)}")
    for r in rows:
        print(f"  - {r['target'][:24]:24} {r['status']}")
    print(f"[P14-decide] audit -> {OUT_MD}")


def _fmt(v: Any, nd: int = 2) -> str:
    return f"{v:.{nd}f}" if isinstance(v, int | float) else "-"


def _write_md(rows: list[dict[str, Any]], *, dry_run: bool) -> None:
    decisions = [r for r in rows if r["status"] == "DECISION"]
    excluded = [r for r in rows if r["status"] != "DECISION"]
    lines = ["# Phase 14 Step 3 — actionable decisions (fresh pool)", ""]
    if dry_run:
        lines.append("> DRY-RUN (no writes, no MD/Discord emitted).")
        lines.append("")
    lines.append(
        f"Candidates: **{len(rows)}** · decisions generated: **{len(decisions)}** · "
        f"excluded: **{len(excluded)}**"
    )
    lines.append("")
    lines.append("## Decisions")
    lines.append("")
    lines.append(
        "| jur | target | ticker | ★ | ref T-1 | premium | ref now | spread | "
        "entry | stop | TP | qty | vivacité |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in sorted(decisions, key=lambda x: -x["stars"]):
        viv = "⚠️ vérifier" if r.get("vivacite") else "ok"
        lines.append(
            f"| {r['jur']} | {r['target'][:22]} | {r['ticker']} | {r['stars']} "
            f"| {_fmt(r.get('ref_t1'))} | {_fmt(r.get('premium_pct'), 1)}% "
            f"| {_fmt(r.get('ref_now'))} | {_fmt(r.get('spread_pct'), 1)}% "
            f"| {_fmt(r.get('entry'))} | {_fmt(r.get('stop'))} | {_fmt(r.get('tp'))} "
            f"| {r.get('qty', '-')} | {viv} |"
        )
    lines.append("")
    lines.append("## Excluded")
    lines.append("")
    lines.append("| jur | target | ★ | reason |")
    lines.append("|---|---|---:|---|")
    for r in excluded:
        lines.append(f"| {r['jur']} | {r['target'][:24]} | {r['stars']} | {r['status']} |")
    lines.append("")
    lines.append(
        "> ⚠️ vivacité : annonce < 2026-02-01 → vérifier que l'OPA est encore "
        "ouverte avant d'exécuter (label non backfillé ≠ encore ouverte)."
    )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="P14 generate decisions for fresh pool")
    p.add_argument("--apply", action="store_true", help="commit + emit (default = dry-run)")
    args = p.parse_args()
    asyncio.run(_process(dry_run=not args.apply))
