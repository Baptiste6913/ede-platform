"""Trade executor (Phase 8) — idempotent order submission + fill bookkeeping.

Submits a :class:`TradeRequest` as a server-side bracket and records its
lifecycle in the `trades` table:

- **Idempotency** — `trade_id` already SUBMITTED/FILLED/REJECTED/CANCELLED ⇒
  no-op (retry-safe). A second open trade for the same deal is skipped.
- **Ramp-up** — a request flagged ``requires_approval`` and not yet approved is
  persisted as PENDING and *not* sent; calling ``submit(..., approved=True)``
  later places the existing PENDING row.
- **Fill** — on a fill, the executor writes back FILLED and updates
  `paper_positions` (BUY ⇒ open/average; SELL ⇒ close + realised P&L).

IBKR interaction goes through the injected :class:`IbkrClient`, so the DB logic
is testable against a real session with a faked broker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import PaperPosition, Trade
from src.trading.bracket_builder import build_bracket, to_ib_orders
from src.trading.decision_engine import TradeRequest

log = structlog.get_logger()

_TERMINAL = ("SUBMITTED", "FILLED", "REJECTED", "CANCELLED")
_OPEN = ("SUBMITTED", "FILLED")


def _dec(value: float) -> Decimal:
    return Decimal(str(value))


class TradeExecutor:
    def __init__(self, ibkr: Any) -> None:
        self.ibkr = ibkr

    async def _qualify(self, request: TradeRequest) -> Any | None:
        if request.symbol and request.exchange:
            return await self.ibkr.qualify_contract(
                request.symbol, request.exchange, request.currency
            )
        if request.isin:
            return await self.ibkr.qualify_by_isin(
                request.isin, request.exchange or "SMART", request.currency
            )
        return None

    async def submit(
        self, session: AsyncSession, request: TradeRequest, *, approved: bool = False
    ) -> Trade | None:
        """Submit (or hold for approval) a TradeRequest. Idempotent on trade_id."""
        existing = await session.scalar(select(Trade).where(Trade.trade_id == request.trade_id))
        if existing is not None and existing.status in _TERMINAL:
            return existing  # already acted on — idempotent no-op

        if existing is None:
            dup = await session.scalar(
                select(Trade).where(Trade.deal_id == request.deal_id, Trade.status.in_(_OPEN))
            )
            if dup is not None:
                log.info("executor_skip_open_deal", deal_id=request.deal_id)
                return None

        effective_approved = approved or not request.requires_approval
        trade = existing or Trade(
            trade_id=request.trade_id,
            deal_id=request.deal_id,
            side=request.side,
            quantity=request.quantity,
            limit_price=_dec(request.limit_price),
            stop_loss_price=_dec(request.stop_loss_price),
            take_profit_price=(
                _dec(request.take_profit_price) if request.take_profit_price is not None else None
            ),
            status="PENDING",
            requires_approval=request.requires_approval,
            rationale=request.rationale,
        )
        trade.approved = effective_approved
        if existing is None:
            session.add(trade)

        if not effective_approved:
            await session.commit()
            log.info("executor_pending_approval", trade_id=request.trade_id)
            return trade

        contract = await self._qualify(request)
        if contract is None:
            trade.status = "REJECTED"
            trade.rejection_reason = "ticker_unresolved"
            await session.commit()
            log.warning("executor_rejected_unresolved", trade_id=request.trade_id)
            return trade

        base = int(self.ibkr.next_order_id())
        legs = build_bracket(
            qty=request.quantity,
            entry_limit=request.limit_price,
            stop_price=request.stop_loss_price,
            take_profit_price=request.take_profit_price,
            parent_id=base,
        )
        orders = to_ib_orders(legs)
        for order in orders:
            self.ibkr.place_order(contract, order)
        trade.ibkr_order_id = str(orders[0].orderId)
        trade.ibkr_stop_order_id = str(orders[1].orderId)
        trade.status = "SUBMITTED"
        await session.commit()
        log.info(
            "executor_submitted",
            trade_id=request.trade_id,
            deal_id=request.deal_id,
            qty=request.quantity,
        )
        return trade

    async def mark_filled(
        self,
        session: AsyncSession,
        trade: Trade,
        filled_price: float,
        filled_quantity: int,
    ) -> Trade:
        """Record an entry/exit fill and update the paper position."""
        trade.status = "FILLED"
        trade.filled_price = _dec(filled_price)
        trade.filled_quantity = filled_quantity
        trade.filled_at = datetime.now(UTC)
        await self._apply_fill_to_position(session, trade, filled_price, filled_quantity)
        await session.commit()
        log.info("executor_filled", trade_id=trade.trade_id, price=filled_price)
        return trade

    async def mark_rejected(self, session: AsyncSession, trade: Trade, reason: str) -> Trade:
        trade.status = "REJECTED"
        trade.rejection_reason = reason
        await session.commit()
        return trade

    async def _apply_fill_to_position(
        self,
        session: AsyncSession,
        trade: Trade,
        filled_price: float,
        filled_quantity: int,
    ) -> None:
        pos = await session.scalar(
            select(PaperPosition).where(
                PaperPosition.deal_id == trade.deal_id,
                PaperPosition.status == "open",
            )
        )
        fill_eur = _dec(filled_price) * filled_quantity

        if trade.side == "BUY":
            if pos is None:
                session.add(
                    PaperPosition(
                        deal_id=trade.deal_id,
                        entry_price=_dec(filled_price),
                        size_eur=fill_eur,
                        side="long",
                        status="open",
                    )
                )
            else:
                total = pos.size_eur + fill_eur
                # entry weighted by euro size (qty is not stored on the position).
                pos.entry_price = (
                    pos.entry_price * pos.size_eur + _dec(filled_price) * fill_eur
                ) / total
                pos.size_eur = total
            return

        # SELL ⇒ close the open long position and realise P&L.
        if pos is None:
            log.warning("executor_sell_no_position", deal_id=trade.deal_id)
            return
        pos.exit_price = _dec(filled_price)
        pos.close_ts = datetime.now(UTC)
        pos.status = "closed"
        if pos.entry_price and pos.entry_price > 0:
            pnl = (_dec(filled_price) / pos.entry_price - Decimal(1)) * pos.size_eur
            pos.pnl_eur = pnl
            trade.pnl_realized = pnl
