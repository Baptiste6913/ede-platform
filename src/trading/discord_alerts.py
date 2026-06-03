"""Discord alerts (Phase 8) — outbound webhook notifications + command parsing.

Adapted from Finance-V4 `discord_notifier.py`: posts via `httpx`, **never
raises** (alerting must not break trading), and is a no-op when no webhook is
configured. Trade/lifecycle alerts go to the *alerts* webhook; the daily P&L
summary goes to the *digest* webhook.

Security: alerts never include the account id or any secret.

`parse_command` turns an inbound Discord message into a control action
(``!stop`` / ``approve <trade_id>`` / ``status``) for the kill switch + ramp-up
approval flow; the HTTP endpoint that receives commands is wired in the
scheduler (Step 8).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from src.core.settings import Settings

if TYPE_CHECKING:
    from src.trading.decision_engine import TradeRequest

log = structlog.get_logger()

PostFn = Callable[[str, dict[str, Any]], Awaitable[None]]

_HTTP_ERROR_STATUS = 400
_APPROVE_ARGC = 2


class DiscordAlerts:
    """Outbound Discord webhook alerts (never raises)."""

    def __init__(
        self,
        webhook_alerts: str = "",
        webhook_digest: str = "",
        post_fn: PostFn | None = None,
    ) -> None:
        self._alerts = webhook_alerts
        self._digest = webhook_digest or webhook_alerts
        self._post_fn = post_fn

    @classmethod
    def from_settings(cls, settings: Settings) -> DiscordAlerts:
        return cls(
            webhook_alerts=settings.discord_webhook_alerts.get_secret_value(),
            webhook_digest=settings.discord_webhook_digest.get_secret_value(),
        )

    @property
    def enabled(self) -> bool:
        return bool(self._alerts)

    async def _post_payload(self, url: str, payload: dict[str, Any]) -> None:
        if not url:
            return
        if self._post_fn is not None:
            await self._post_fn(url, payload)
            return
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code >= _HTTP_ERROR_STATUS:
                    log.warning("discord_http_error", status=resp.status_code)
        except Exception as exc:
            log.warning("discord_send_error", error=str(exc))

    async def _post(self, url: str, content: str) -> None:
        await self._post_payload(url, {"content": content})

    # ------------------------------------------------------------- decision
    async def decision_alert(
        self, req: TradeRequest, deal: Any, *, today: date | None = None
    ) -> None:
        """Rich embed for a produced decision — the scannable real-time alert;
        the MD file (footer reference) holds the full detail. Never raises;
        independent of paper execution. Missing fields render as N/A."""
        from src.output.decision_md import decision_view

        v = decision_view(req, deal, today=today or date.today())
        cur = v["currency"]
        embed = {
            "title": f"🟢 ACHAT — {v['target']} ({v['juridiction']})",
            "color": 0x2ECC71,
            "fields": [
                {"name": "Ticker IBKR", "value": v["ticker_ibkr"], "inline": True},
                {"name": "Ticker yfinance", "value": v["ticker_yf"], "inline": True},
                {
                    "name": "Entry / Stop / TP",
                    "value": f"{v['entry']} / {v['stop']} / {v['tp']} {cur}",
                    "inline": False,
                },
                {
                    "name": "Sizing",
                    "value": f"{v['qty']} actions (~{v['notional']} {cur}, {v['pct_capital']})",
                    "inline": False,
                },
                {"name": "Score", "value": f"{v['score']} (p={v['proba']})", "inline": True},
                {"name": "Premium", "value": v["premium"], "inline": True},
                {"name": "Stratégie", "value": v["strategy"], "inline": False},
            ],
            "footer": {"text": f"Filing {v['filing']} · annonce {v['announce']} · {v['md_name']}"},
        }
        await self._post_payload(self._alerts, {"embeds": [embed]})

    # ------------------------------------------------------------- lifecycle
    async def trade_generated(
        self, deal: str, qty: int, price: float, rampup_idx: int, rampup_total: int
    ) -> None:
        await self._post(
            self._alerts,
            f"🟢 New trade pending approval (ramp-up {rampup_idx}/{rampup_total}): "
            f"{deal} buy {qty} @ {price:.2f}",
        )

    async def trade_submitted(self, deal: str, qty: int, price: float) -> None:
        await self._post(self._alerts, f"📤 Order submitted: {deal} buy {qty} @ {price:.2f}")

    async def trade_filled(self, deal: str, price: float, p_completion: float) -> None:
        await self._post(
            self._alerts, f"✅ Fill confirmed: {deal} @ {price:.2f} (p={p_completion:.2f})"
        )

    async def trade_rejected(self, deal: str, reason: str) -> None:
        await self._post(self._alerts, f"❌ Order rejected: {deal} — {reason}")

    async def frozen_price_warning(self, deal: str) -> None:
        await self._post(
            self._alerts, f"⚠️ Trade priced on a FROZEN quote (stale up to ~24h): {deal}"
        )

    async def stop_hit(self, deal: str, pnl: float) -> None:
        await self._post(self._alerts, f"🛑 Stop-loss hit: {deal}, P&L €{pnl:,.0f}")

    async def profit_taken(self, deal: str, pnl: float) -> None:
        await self._post(self._alerts, f"💰 Take-profit hit: {deal}, P&L €{pnl:,.0f}")

    async def heartbeat(self, positions: int, pnl_pct: float) -> None:
        await self._post(
            self._alerts, f"🟢 System alive — {positions} positions, P&L {pnl_pct:+.2%}"
        )

    async def kill_switch_active(self) -> None:
        await self._post(self._alerts, "🚨 Kill switch active — trading halted")

    async def daily_loss_limit(self, limit_pct: float) -> None:
        await self._post(
            self._alerts, f"🛑 Daily loss limit hit ({-limit_pct:.0%}) — system shutdown"
        )

    # --------------------------------------------------------------- digest
    async def daily_pnl(self, portfolio_value: float, pnl_pct: float, positions: int) -> None:
        await self._post(
            self._digest,
            f"📊 Daily P&L — portfolio €{portfolio_value:,.0f}, "
            f"{pnl_pct:+.2%}, {positions} positions",
        )


def parse_command(text: str) -> tuple[str, str | None] | None:
    """Parse an inbound Discord control message.

    Returns ("stop", None) | ("approve", trade_id) | ("status", None) | None.
    """
    t = text.strip()
    low = t.lower()
    if low in ("!stop", "stop"):
        return ("stop", None)
    if low in ("!status", "status"):
        return ("status", None)
    parts = t.split()
    if len(parts) == _APPROVE_ARGC and parts[0].lower() in ("approve", "!approve"):
        return ("approve", parts[1])
    return None
