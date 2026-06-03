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
from typing import TYPE_CHECKING, Any, Final
from zoneinfo import ZoneInfo

import structlog

from src.core.settings import Settings, get_settings
from src.trading.decision_engine import DealCandidate, DecisionEngine, TradeRequest
from src.trading.discord_alerts import DiscordAlerts
from src.trading.executor import TradeExecutor
from src.trading.price_provider import PriceProvider, YFinancePriceProvider

if TYPE_CHECKING:
    from src.output.decision_md import DecisionSink
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
    """Outcome of one daily cycle.

    ``decisions`` lists every TradeRequest produced this cycle, **independent of
    execution** (Phase 13: decisions are computed without IBKR). ``submitted`` /
    ``pending_approval`` track the downstream, optional paper-execution step.
    """

    halted: str | None = None
    decisions: list[str] = field(default_factory=list)
    submitted: list[str] = field(default_factory=list)
    pending_approval: list[str] = field(default_factory=list)
    skipped: int = 0
    execution_skipped: int = 0


class TradingScheduler:
    """Wires resolver/engine/executor/safeguards/discord around the IBKR client."""

    def __init__(
        self,
        ibkr: Any,
        executor: TradeExecutor | None,
        engine: DecisionEngine,
        discord: DiscordAlerts,
        kill_switch: KillSwitch | None = None,
        settings: Settings | None = None,
        price_provider: PriceProvider | None = None,
        decision_sink: DecisionSink | None = None,
    ) -> None:
        self.ibkr: Any = ibkr
        self.executor = executor
        self.engine = engine
        self.discord = discord
        self.kill_switch = kill_switch or KillSwitch()
        self.settings = settings or get_settings()
        # Decision-time price source — non-broker by default (Phase 13). The
        # decision calculation never touches IBKR; pricing comes from here.
        self.price_provider: PriceProvider = price_provider or YFinancePriceProvider()
        # Decision surface — writes the actionable MD + index per decision,
        # independent of paper execution (Phase 13).
        if decision_sink is None:
            from src.output.decision_md import MarkdownDecisionSink

            decision_sink = MarkdownDecisionSink()
        self.decision_sink: DecisionSink = decision_sink

    def _broker_available(self) -> bool:
        """True when a paper-execution path exists (executor + connected IBKR)."""
        if self.executor is None or self.ibkr is None:
            return False
        return bool(getattr(self.ibkr, "is_connected", True))

    async def _snapshot(self, cand: DealCandidate) -> Any | None:
        """Decision-time reference price — from the price provider, not IBKR."""
        return await self.price_provider.get_snapshot(cand)

    async def _emit_decision(self, session: object, req: TradeRequest) -> None:
        """Surface a produced decision (MD + index). Best-effort: a sink/IO
        failure must not abort the cycle nor block paper execution."""
        if session is None:
            return
        from src.core.models import Deal

        deal = await session.get(Deal, req.deal_id)  # type: ignore[attr-defined]
        if deal is None:
            return
        try:
            await self.decision_sink.emit(req, deal)
        except Exception as exc:
            log.warning("decision_sink_failed", trade_id=req.trade_id, error=str(exc))
        try:
            await self.discord.decision_alert(req, deal)
        except Exception as exc:
            log.warning("discord_decision_failed", trade_id=req.trade_id, error=str(exc))

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
                snapshot = await self._snapshot(cand)
                if snapshot is None:
                    summary.skipped += 1
                    continue
                req = self.engine.evaluate(cand, snapshot, net_liquidation, open_positions, rampup)
                if req is None:
                    summary.skipped += 1
                    continue
                # Decision is produced regardless of execution (Phase 13):
                # surface it (MD + index) before any broker interaction.
                summary.decisions.append(req.trade_id)
                await self._emit_decision(session, req)

                # Downstream, optional paper execution — skip gracefully when the
                # broker is unavailable; the decision still stands.
                if not self._broker_available():
                    summary.execution_skipped += 1
                    log.info(
                        "paper_execution_skipped",
                        reason="ibkr_unavailable",
                        trade_id=req.trade_id,
                        deal_id=req.deal_id,
                    )
                    continue
                if cooldown_active(
                    await store.last_order_ts(), now, self.settings.trading_order_cooldown_min
                ):
                    summary.execution_skipped += 1
                    continue
                trade = await self.executor.submit(session, req)  # type: ignore[union-attr,arg-type]
                if trade is None:
                    summary.execution_skipped += 1
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


# Offer-price quality flags that must never reach the trade loop: a mixed /
# share-exchange offer has no scalar price (P9.1a), and failed_validation /
# manual_review are explicit do-not-trade states (P9.1c). verified_cash and
# suspect_low_unverified stay tradable. Subset of
# src.core.enums.OFFER_PRICE_QUALITY_FLAGS. Behaviour-preserving today
# (suspect_mixed already has a NULL price the decision engine skips); this makes
# the exclusion explicit and future-proofs the P9.1c flags.
UNTRADEABLE_OFFER_PRICE_FLAGS: Final[tuple[str, ...]] = (
    "suspect_mixed",
    "failed_validation",
    "manual_review",
)


async def load_candidates(
    session: object,
    resolver: object,
    min_stars: int = 3,
    allowed_jurisdictions: list[str] | None = None,
    openfigi: object | None = None,
    home_venue_strict_jurisdictions: list[str] | None = None,
) -> list[DealCandidate]:
    """Load pending, sufficiently-scored deals and resolve their tickers.

    ``allowed_jurisdictions`` scopes the pipeline (Phase 13 = ``["DE", "FR"]``);
    ``None`` means no jurisdiction filter. Deals whose ``offer_price_quality_flag``
    is in ``UNTRADEABLE_OFFER_PRICE_FLAGS`` are excluded (no reliable scalar price).

    When ``openfigi`` is provided, a deal that has never been resolved
    (``ticker_resolution_flag IS NULL``) is resolved once and its ticker
    persisted (Phase 13 live wiring); the mutation is committed by the caller's
    cycle. The candidate's ``yahoo_ticker`` is read from the persisted
    ``trading_ticker_yf`` — the decision-time price provider keys on it.

    Confidence gate (Phase 13): in a jurisdiction listed in
    ``home_venue_strict_jurisdictions`` (FR), a deal is auto-tradable ONLY when
    it resolved to ``home_venue``; growth / venue_fallback / no_match / corrupt
    flags fall to manual_review (excluded here). The gate runs AFTER live
    resolution so a fresh deal is resolved first, then gated on its outcome.
    Non-gated jurisdictions (DE) keep their existing ISIN-path behaviour.
    """
    from sqlalchemy import select

    from src.core.models import Deal, Score
    from src.pricing.ticker_resolution import (
        HOME_VENUE_FLAG,
        needs_resolution,
        resolve_and_persist,
    )

    strict = {j.upper() for j in (home_venue_strict_jurisdictions or [])}
    stmt = (
        select(Deal, Score)
        .join(Score, Score.deal_id == Deal.id)
        .where(
            Score.score_stars >= min_stars,
            Deal.completion_label.is_(None),
            Deal.offer_price_quality_flag.not_in(UNTRADEABLE_OFFER_PRICE_FLAGS),
        )
    )
    if allowed_jurisdictions:
        stmt = stmt.where(Deal.juridiction.in_(allowed_jurisdictions))
    rows = (await session.execute(stmt)).all()  # type: ignore[attr-defined]
    out: list[DealCandidate] = []
    for deal, score in rows:
        if openfigi is not None and needs_resolution(deal):
            await resolve_and_persist(deal, openfigi)  # type: ignore[arg-type]
        if deal.juridiction in strict and deal.ticker_resolution_flag != HOME_VENUE_FLAG:
            log.info(
                "candidate_manual_review",
                deal_id=deal.id,
                juridiction=deal.juridiction,
                flag=deal.ticker_resolution_flag,
            )
            continue
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
                yahoo_ticker=deal.trading_ticker_yf,
            )
        )
    return out
