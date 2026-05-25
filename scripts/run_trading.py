"""Phase 8 trading runner — wires the scheduler and runs the daily cycle.

    .venv/Scripts/python.exe scripts/run_trading.py --once   # single cycle (Step 11)
    .venv/Scripts/python.exe scripts/run_trading.py          # loop at 9h Paris

Long-running mode sleeps until the next DST-aware 9h Paris, runs one cycle, and
emits a Discord heartbeat. The forever-loop + live IBKR fills are validated in
the Step-11 live run; `--once` is the live-first-trade entry.

Paper only — the IbkrClient paper-port guard refuses any non-paper connection.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow `from src...` when run as a plain script (scripts/ dir is on sys.path,
# not the repo root).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog

from src.core.db import get_sessionmaker
from src.core.settings import get_settings
from src.trading.decision_engine import DecisionEngine
from src.trading.discord_alerts import DiscordAlerts
from src.trading.executor import TradeExecutor
from src.trading.ibkr_client import IbkrClient
from src.trading.safeguards import KillSwitch
from src.trading.scheduler import TradingScheduler, load_candidates, next_paris_time

log = structlog.get_logger()


async def _run_once() -> None:
    settings = get_settings()
    ibkr = IbkrClient(settings)
    await ibkr.connect()
    try:
        from src.trading.ticker_resolver import TickerResolver

        scheduler = TradingScheduler(
            ibkr=ibkr,
            executor=TradeExecutor(ibkr),
            engine=DecisionEngine.from_settings(settings),
            discord=DiscordAlerts.from_settings(settings),
            kill_switch=KillSwitch(),
            settings=settings,
        )
        resolver = TickerResolver.from_file()
        net_liq = await ibkr.get_net_liquidation()
        async with get_sessionmaker()() as session:
            candidates = await load_candidates(
                session,
                resolver,
                settings.trading_min_score_stars,
                allowed_jurisdictions=settings.trading_allowed_jurisdictions,
            )
            summary = await scheduler.run_daily_cycle(session, candidates, net_liq)
        log.info(
            "trading_cycle_done",
            halted=summary.halted,
            submitted=len(summary.submitted),
            pending=len(summary.pending_approval),
            skipped=summary.skipped,
        )
    finally:
        await ibkr.disconnect()


async def _run_forever() -> None:
    while True:
        wake = next_paris_time(datetime.now(UTC), 9)
        delay = (wake - datetime.now(UTC)).total_seconds()
        log.info("trading_sleep_until", wake_utc=wake.isoformat(), seconds=int(delay))
        await asyncio.sleep(max(delay, 0))
        if KillSwitch().is_active():
            log.warning("trading_halted_kill_switch")
            continue
        try:
            await _run_once()
        except Exception as exc:
            log.error("trading_cycle_error", error=str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(description="EDE Phase 8 trading runner")
    parser.add_argument("--once", action="store_true", help="run a single cycle then exit")
    args = parser.parse_args()
    if args.once:
        asyncio.run(_run_once())
    else:
        asyncio.run(_run_forever())


if __name__ == "__main__":
    main()
