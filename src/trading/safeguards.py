"""Safeguards (Phase 8) — kill switch, daily loss limit, cooldown, ramp-up.

Layered protections around the executor:

- **KillSwitch** — presence of ``data/kill_switch.flag`` halts trading before the
  next order (flipped by the Discord ``!stop`` command or by hand). File-based so
  it works without a DB write and survives restarts.
- **Daily loss limit** — if NetLiquidation drops ``limit_pct`` below the day's
  baseline, trading auto-shuts down.
- **Position cap** — refuse new entries beyond ``max_positions``.
- **Order cooldown** — minimum gap between consecutive orders.
- **Ramp-up** — count of validated trades persisted in ``system_state``; the
  first N trades require manual approval.

Pure checks are module functions; persistent counters live in
:class:`SystemStateStore` (the ``system_state`` table, migration 0013).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import SystemState

log = structlog.get_logger()

DEFAULT_KILL_SWITCH_PATH = Path("data/kill_switch.flag")

KEY_RAMPUP = "rampup_trades_validated"
KEY_DAILY_BASELINE = "daily_nlv_baseline"
KEY_DAILY_BASELINE_DATE = "daily_nlv_baseline_date"
KEY_LAST_ORDER_TS = "last_order_ts"


class KillSwitch:
    """File-based emergency stop. Presence of the flag file = halt."""

    def __init__(self, path: Path | str = DEFAULT_KILL_SWITCH_PATH) -> None:
        self.path = Path(path)

    def is_active(self) -> bool:
        return self.path.exists()

    def activate(self, reason: str = "halt") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(reason, encoding="utf-8")
        log.warning("kill_switch_activated", reason=reason)

    def deactivate(self) -> None:
        self.path.unlink(missing_ok=True)
        log.info("kill_switch_deactivated")


# ------------------------------------------------------------- pure checks
def position_cap_reached(open_count: int, max_positions: int = 5) -> bool:
    return open_count >= max_positions


def daily_loss_breached(
    net_liquidation_now: float, baseline: float, limit_pct: float = 0.02
) -> bool:
    """True if NetLiq is ``limit_pct`` or more below the day's baseline."""
    if baseline <= 0:
        return False
    drawdown = (baseline - net_liquidation_now) / baseline
    return drawdown >= limit_pct


def cooldown_active(last_order_ts: datetime | None, now: datetime, cooldown_min: int = 60) -> bool:
    if last_order_ts is None:
        return False
    return now - last_order_ts < timedelta(minutes=cooldown_min)


# ----------------------------------------------------- persistent counters
class SystemStateStore:
    """Async key/value accessor over the ``system_state`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> str | None:
        row = await self.session.get(SystemState, key)
        return row.value if row is not None else None

    async def set(self, key: str, value: object) -> None:
        row = await self.session.get(SystemState, key)
        if row is None:
            self.session.add(SystemState(key=key, value=str(value)))
        else:
            row.value = str(value)
        await self.session.flush()

    async def get_int(self, key: str, default: int = 0) -> int:
        v = await self.get(key)
        return int(v) if v is not None else default

    async def get_float(self, key: str, default: float = 0.0) -> float:
        v = await self.get(key)
        return float(v) if v is not None else default

    # ---- ramp-up ----
    async def rampup_validated(self) -> int:
        return await self.get_int(KEY_RAMPUP, 0)

    async def increment_rampup(self) -> int:
        n = await self.rampup_validated() + 1
        await self.set(KEY_RAMPUP, n)
        return n

    # ---- daily loss baseline ----
    async def ensure_daily_baseline(
        self, net_liquidation: float, today: date | None = None
    ) -> float:
        """Set (and return) the day's NetLiq baseline; resets on a new day."""
        today_str = (today or datetime.now(UTC).date()).isoformat()
        if await self.get(KEY_DAILY_BASELINE_DATE) != today_str:
            await self.set(KEY_DAILY_BASELINE, net_liquidation)
            await self.set(KEY_DAILY_BASELINE_DATE, today_str)
            return float(net_liquidation)
        return await self.get_float(KEY_DAILY_BASELINE, net_liquidation)

    # ---- order cooldown ----
    async def last_order_ts(self) -> datetime | None:
        v = await self.get(KEY_LAST_ORDER_TS)
        return datetime.fromisoformat(v) if v else None

    async def set_last_order_now(self, now: datetime | None = None) -> None:
        await self.set(KEY_LAST_ORDER_TS, (now or datetime.now(UTC)).isoformat())
