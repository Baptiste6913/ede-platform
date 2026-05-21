"""IBKR client wrapper (Phase 8) — connection, qualify, price, account, orders.

Thin async wrapper around `ib_async` adapted from Finance-V4
(`src/execution/ibkr_client.py`) for EDE's needs:

- Flat `Settings` config (`ibkr_host`/`ibkr_port`/`ibkr_client_id`/`ibkr_paper`).
- EUR equities, FR/IT/DE; long-only (no options / historical bars).
- **Paper guard**: refuses to connect unless `ibkr_paper` and a paper port.
- **Delayed market data** (`reqMarketDataType(3)`, free tier) per Step-0 decision.
- SDK-free dataclasses at the boundary (`PriceSnapshot`, `AccountSnapshot`,
  `BrokerPosition`) so the rest of the platform never imports `ib_async`.

The broker SDK is `ib_async`, which is untyped; per the mypy override for
`src.trading.*` we accept Any-leaning values from it and convert to our
dataclasses here.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any

import structlog

from src.core.settings import Settings, get_settings

log = structlog.get_logger()

# IBKR socket ports that correspond to a PAPER session. Connecting anywhere
# else is refused — hard no-real-money guardrail (brief guardrail).
PAPER_PORTS = frozenset({7497, 4002})

# Market-data type: 3 = delayed (free). Step-0 decision #2.
DELAYED_MARKET_DATA = 3


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    """SDK-free price snapshot. Missing/invalid quotes are ``None``.

    Borsa Italiana (BVME) delayed feed returns no bid/ask (Step-0 finding):
    those come back as ``None`` and callers fall back to ``last``.
    """

    bid: float | None
    ask: float | None
    last: float | None
    close: float | None
    market_data_type: int

    @property
    def mid(self) -> float | None:
        """Mid price when both bid and ask are present, else ``None``."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2.0
        return None

    @property
    def has_quote(self) -> bool:
        """True if any usable price (mid or last) is available."""
        return self.mid is not None or self.last is not None


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """SDK-free account summary (the paper `DU…` account)."""

    account_id: str
    net_liquidation: float
    total_cash: float
    currency: str


@dataclass(frozen=True, slots=True)
class BrokerPosition:
    """SDK-free open position as reported by the broker."""

    symbol: str
    exchange: str
    quantity: float
    avg_cost: float
    account: str


def _clean_price(value: Any) -> float | None:
    """Coerce an ib_async tick field to a positive float or ``None``.

    ib_async uses NaN for "no data" and -1 for "not available on this feed".
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or f <= 0:
        return None
    return f


class IbkrClient:
    """Async IBKR client over ``ib_async`` (paper trading only).

    ``ib`` is injectable for tests; in production it is created lazily in
    :meth:`connect`.
    """

    def __init__(self, settings: Settings | None = None, ib: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self.ib: Any = ib
        self._connected = False

    # ------------------------------------------------------------------ guard
    def _guard_paper(self) -> None:
        if not self.settings.ibkr_paper or self.settings.ibkr_port not in PAPER_PORTS:
            raise RuntimeError(
                "IBKR paper guard: refusing to connect "
                f"(ibkr_paper={self.settings.ibkr_paper}, port={self.settings.ibkr_port}). "
                f"Paper ports are {sorted(PAPER_PORTS)}."
            )

    # ------------------------------------------------------------ connection
    async def connect(self) -> None:
        """Connect to the paper Gateway/TWS and select delayed market data."""
        self._guard_paper()
        if self.ib is None:
            from ib_async import IB

            self.ib = IB()
        await self.ib.connectAsync(
            self.settings.ibkr_host,
            self.settings.ibkr_port,
            clientId=self.settings.ibkr_client_id,
            timeout=15,
        )
        self.ib.disconnectedEvent += self._on_disconnect
        self.ib.reqMarketDataType(DELAYED_MARKET_DATA)
        self._connected = True
        log.info(
            "ibkr_connected",
            host=self.settings.ibkr_host,
            port=self.settings.ibkr_port,
            client_id=self.settings.ibkr_client_id,
        )

    def _on_disconnect(self) -> None:
        self._connected = False
        log.warning("ibkr_disconnected")

    async def reconnect(self, attempts: int = 3) -> bool:
        """Reconnect with linear backoff. Returns True on success."""
        for attempt in range(attempts):
            await asyncio.sleep(5 * (attempt + 1))
            try:
                await self.connect()
            except Exception as exc:
                log.warning("ibkr_reconnect_failed", attempt=attempt, error=str(exc))
                continue
            log.info("ibkr_reconnected", attempt=attempt)
            return True
        return False

    @property
    def is_connected(self) -> bool:
        return self._connected and self.ib is not None and bool(self.ib.isConnected())

    async def disconnect(self) -> None:
        if self.ib is not None and self.ib.isConnected():
            self.ib.disconnect()
        self._connected = False
        log.info("ibkr_disconnected_graceful")

    # ------------------------------------------------------------- contracts
    async def qualify_contract(
        self, symbol: str, exchange: str, currency: str = "EUR"
    ) -> Any | None:
        """Qualify a stock; try the primary exchange directly then SMART routing.

        Returns the qualified contract (``conId`` populated) or ``None`` when
        no security definition is found (logged, never raised) — Step-0 found
        e.g. Sanofi/SAN needs resolver attention while AIR on the same SBF works.
        """
        from ib_async import Stock

        for routing in (exchange, "SMART"):
            contract = Stock(symbol, routing, currency, primaryExchange=exchange)
            try:
                await self.ib.qualifyContractsAsync(contract)
            except Exception as exc:
                log.warning("qualify_failed", symbol=symbol, exchange=routing, error=str(exc))
            if getattr(contract, "conId", 0):
                return contract
        log.warning("qualify_no_definition", symbol=symbol, exchange=exchange)
        return None

    # ----------------------------------------------------------- market data
    async def get_current_price(self, contract: Any) -> PriceSnapshot:
        """Delayed snapshot for a qualified contract (bid/ask/last/close)."""
        self.ib.reqMarketDataType(DELAYED_MARKET_DATA)
        tickers = await self.ib.reqTickersAsync(contract)
        tk = tickers[0]
        return PriceSnapshot(
            bid=_clean_price(getattr(tk, "bid", None)),
            ask=_clean_price(getattr(tk, "ask", None)),
            last=_clean_price(getattr(tk, "last", None)),
            close=_clean_price(getattr(tk, "close", None)),
            market_data_type=int(getattr(tk, "marketDataType", DELAYED_MARKET_DATA)),
        )

    # --------------------------------------------------------------- account
    async def get_account_summary(self) -> AccountSnapshot:
        """Summary of the paper ``DU…`` account (NetLiquidation, cash)."""
        rows = await self.ib.accountSummaryAsync()
        paper_accounts = sorted({r.account for r in rows if r.account.startswith("DU")})
        if not paper_accounts:
            raise RuntimeError("No DU… paper account found in accountSummary.")
        account_id = paper_accounts[0]
        tags = {r.tag: r for r in rows if r.account == account_id}
        net = tags.get("NetLiquidation")
        cash = tags.get("TotalCashValue")
        return AccountSnapshot(
            account_id=account_id,
            net_liquidation=float(net.value) if net else 0.0,
            total_cash=float(cash.value) if cash else 0.0,
            currency=(net.currency if net else "EUR"),
        )

    async def get_net_liquidation(self) -> float:
        """Live NetLiquidation — drives dynamic position sizing (decision #1)."""
        return (await self.get_account_summary()).net_liquidation

    # ------------------------------------------------------------- positions
    async def get_positions(self) -> list[BrokerPosition]:
        positions = await self.ib.reqPositionsAsync()
        out: list[BrokerPosition] = []
        for p in positions:
            contract = p.contract
            out.append(
                BrokerPosition(
                    symbol=getattr(contract, "symbol", "?"),
                    exchange=getattr(contract, "exchange", "?")
                    or getattr(contract, "primaryExchange", "?"),
                    quantity=float(p.position),
                    avg_cost=float(p.avgCost),
                    account=p.account,
                )
            )
        return out

    # ----------------------------------------------------------------- orders
    def place_order(self, contract: Any, order: Any) -> Any:
        """Submit one order leg to IBKR; returns the ib_async ``Trade``.

        Bracket assembly + idempotency live in the executor (Step 5); this is
        the low-level submit only.
        """
        return self.ib.placeOrder(contract, order)
