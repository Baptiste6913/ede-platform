"""Trading scheduler (Phase 8) — DST-aware daily cycle + heartbeat.

Orchestrates the pieces into a daily run:

- **next_paris_time** — pure, DST-aware (`Europe/Paris`, decision #4): the 9h
  Paris cron is 07:00 UTC in summer (CEST) and 08:00 UTC in winter (CET).
- **run_daily_cycle** — kill-switch + daily-loss guards first, then for each
  candidate resolve→qualify→price→evaluate→submit, honouring cooldown, position
  cap, and ramp-up; alerts via Discord.
- **run_forever** — the thin long-running loop (validated in the Step-11 live
  run), with IBKR auto-reconnect and graceful kill-switch shutdown.

The cycle and the time maths are unit-testable with mocks / fixed clocks; the
forever-loop is intentionally thin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog

from src.core.settings import Settings, get_settings
from src.trading.decision_engine import DealCandidate, DecisionEngine, TradeRequest
from src.trading.discord_alerts import DiscordAlerts
from src.trading.executor import TradeExecutor
from src.trading.safeguards import (
    KillSwitch,
    SystemStateStore,
    cooldown_active,
    daily_loss_breached,
)

log = structlog.get_logger()


def next_paris_time(now_utc: datetime, hour: int, tz: str = "Europe/Paris") -> datetime:
    """Next UTC instant at which it is ``hour:00`` local Paris time (DST-aware)."""
    zone = ZoneInfo(tz)
    now_local = now_utc.astimezone(zone)
    target = now_local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now_local:
        target += timedelta(days=1)
    return target.astimezone(UTC)


@dataclass(slots=True)
class CycleSummary:
    """Outcome of one daily cycle."""

    halted: str | None = None
    submitted: list[str] = field(default_factory=list)
    pending_approval: list[str] = field(default_factory=list)
    skipped: int = 0


class TradingScheduler:
    """Wires resolver/engine/executor/safeguards/discord around the IBKR client."""

    def __init__(
        self,
        ibkr: Any,
        executor: TradeExecutor,
        engine: DecisionEngine,
        discord: DiscordAlerts,
        kill_switch: KillSwitch | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.ibkr: Any = ibkr
        self.executor = executor
        self.engine = engine
        self.discord = discord
        self.kill_switch = kill_switch or KillSwitch()
        self.settings = settings or get_settings()

    async def _snapshot(self, cand: DealCandidate) -> Any | None:
        """Resolve+qualify the candidate's contract and fetch a price snapshot."""
        if cand.symbol and cand.exchange:
            contract = await self.ibkr.qualify_contract(cand.symbol, cand.exchange, cand.currency)
        elif cand.isin:
            contract = await self.ibkr.qualify_by_isin(cand.isin, cand.exchange or "SMART")
        else:
            return None
        if contract is None:
            return None
        return await self.ibkr.get_current_price(contract)

    async def run_daily_cycle(
        self,
        session: object,
        candidates: list[DealCandidate],
        net_liquidation: float,
        now: datetime | None = None,
    ) -> CycleSummary:
        now = now or datetime.now(UTC)
        summary = CycleSummary()
        try:
            if self.kill_switch.is_active():
                await self.discord.kill_switch_active()
                summary.halted = "kill_switch"
                return summary

            store = SystemStateStore(session)  # type: ignore[arg-type]
            baseline = await store.ensure_daily_baseline(net_liquidation)
            if daily_loss_breached(
                net_liquidation, baseline, self.settings.trading_daily_loss_limit_pct
            ):
                self.kill_switch.activate("daily_loss_limit")
                await self.discord.daily_loss_limit(self.settings.trading_daily_loss_limit_pct)
                summary.halted = "daily_loss"
                return summary

            open_positions = await self._open_position_count(session)
            rampup = await store.rampup_validated()

            for cand in candidates:
                if cooldown_active(
                    await store.last_order_ts(), now, self.settings.trading_order_cooldown_min
                ):
                    summary.skipped += 1
                    continue
                snapshot = await self._snapshot(cand)
                if snapshot is None:
                    summary.skipped += 1
                    continue
                req = self.engine.evaluate(cand, snapshot, net_liquidation, open_positions, rampup)
                if req is None:
                    summary.skipped += 1
                    continue
                trade = await self.executor.submit(session, req)  # type: ignore[arg-type]
                if trade is None:
                    summary.skipped += 1
                    continue
                open_positions = await self._handle_trade(
                    trade, req, store, summary, open_positions, rampup, now
                )
            return summary
        finally:
            # Persist system_state (daily baseline, last-order ts) even when no
            # trade was submitted — otherwise the daily-loss baseline resets
            # every cycle and the safeguard never fires (Step-11 dry-run bug).
            if session is not None:
                await session.commit()  # type: ignore[attr-defined]

    async def _handle_trade(
        self,
        trade: Any,
        req: TradeRequest,
        store: SystemStateStore,
        summary: CycleSummary,
        open_positions: int,
        rampup: int,
        now: datetime,
    ) -> int:
        """Alert + bookkeep one submitted trade; returns the open-position count."""
        if trade.status == "PENDING" and req.requires_approval:
            await self.discord.trade_generated(
                req.deal_target,
                req.quantity,
                req.limit_price,
                rampup + 1,
                self.settings.trading_rampup_required,
            )
            summary.pending_approval.append(req.trade_id)
        elif trade.status == "SUBMITTED":
            open_positions += 1
            await store.set_last_order_now(now)
            await self.discord.trade_submitted(req.deal_target, req.quantity, req.limit_price)
            summary.submitted.append(req.trade_id)
        else:
            summary.skipped += 1
        if req.price_source == "frozen" and trade.status in ("PENDING", "SUBMITTED"):
            await self.discord.frozen_price_warning(req.deal_target)
        return open_positions

    async def _open_position_count(self, session: object) -> int:
        from sqlalchemy import func, select

        from src.core.models import PaperPosition

        result = await session.scalar(  # type: ignore[attr-defined]
            select(func.count()).select_from(PaperPosition).where(PaperPosition.status == "open")
        )
        return int(result or 0)


async def load_candidates(
    session: object,
    resolver: object,
    min_stars: int = 3,
    allowed_jurisdictions: list[str] | None = None,
) -> list[DealCandidate]:
    """Load pending, sufficiently-scored deals and resolve their IBKR tickers.

    ``allowed_jurisdictions`` scopes the pipeline (V1 = ``["DE"]``); ``None``
    means no jurisdiction filter.
    """
    from sqlalchemy import select

    from src.core.models import Deal, Score

    stmt = (
        select(Deal, Score)
        .join(Score, Score.deal_id == Deal.id)
        .where(Score.score_stars >= min_stars, Deal.completion_label.is_(None))
    )
    if allowed_jurisdictions:
        stmt = stmt.where(Deal.juridiction.in_(allowed_jurisdictions))
    rows = (await session.execute(stmt)).all()  # type: ignore[attr-defined]
    out: list[DealCandidate] = []
    for deal, score in rows:
        resolved = resolver.resolve(  # type: ignore[attr-defined]
            deal.target_name,
            deal.juridiction,
            deal.regulator_ref,
            deal.ticker_target,
            deal.ibkr_ticker,
            deal.ibkr_exchange,
        )
        out.append(
            DealCandidate(
                deal_id=deal.id,
                target_name=deal.target_name,
                acquirer_name=deal.acquirer_name,
                juridiction=deal.juridiction,
                offer_price=float(deal.offer_price) if deal.offer_price is not None else None,
                p_completion=float(score.p_completion),
                score_stars=int(score.score_stars),
                symbol=resolved.symbol if resolved else None,
                exchange=resolved.exchange if resolved else None,
                isin=resolved.isin if resolved else None,
                currency=resolved.currency if resolved else "EUR",
            )
        )
    return out
