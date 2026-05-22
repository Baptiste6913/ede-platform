# Trading — Phase 8 paper engine (IBKR)

Long-only merger-arbitrage on FR/IT/DE equities, **paper account only**. The
system turns scored deals into server-side bracket orders on IBKR, with drastic
safeguards and a manual-approval ramp-up.

> **Paper-only guarantee.** `IbkrClient` refuses to connect unless `ibkr_paper`
> is true *and* the port is a paper port (7497 / 4002). There is no code path to
> a live account.

## V1 Scope

Paper trading V1 is scoped to the **DE jurisdiction only** (~42 deals). BaFin
deals carry an **ISIN systematically** (in `regulator_ref` / `ticker_target`),
so ticker resolution is reliable. FR (AMF BDIF) and IT (Consob) do **not**
publish ISIN in `regulator_ref`, making ticker mapping unreliable without
dedicated extraction. Configurable via env:

```
TRADING_ALLOWED_JURISDICTIONS=DE          # default (V1)
TRADING_ALLOWED_JURISDICTIONS=DE,FR,IT    # after Phase-9 ISIN extraction
```

`load_candidates` filters on `settings.trading_allowed_jurisdictions`; the
Step-11 dry-run confirmed 203/209 FR/IT candidates were unresolved, validating
the DE-first scope.

## Architecture

```
                          ┌─────────────── system_state (ramp-up, daily baseline, cooldown)
                          │                 trades (order lifecycle) · paper_positions (state)
   scores + deals (DB) ───┤
                          ▼
  load_candidates ─▶ DecisionEngine.evaluate ─▶ TradeRequest ─▶ TradeExecutor.submit
        │  resolve ticker        │ spread, Kelly size,              │ idempotent (trade_id)
        │  (cache→manual→ISIN)   │ stop/TP, ramp-up flag            │ ramp-up gate
        ▼                        ▼                                  ▼
   TickerResolver        IbkrClient.get_current_price        build_bracket → IBKR
                          (delayed market data, type 3)       (LMT entry + STP + LMT TP, OCA)
                                                                   │
   Discord ◀── DiscordAlerts (10 types) ◀──────────────────────────┘ fills → paper_positions
      │  !stop / approve <id> / status (parse_command)
      ▼
   KillSwitch (data/kill_switch.flag)  ·  scheduler: 9h Paris (DST-aware), 4h heartbeat
```

`scripts/run_trading.py --once` runs a single daily cycle (the Step-11 first
trade); without `--once` it loops, waking at the next DST-aware 9h Paris.

## Position sizing (Kelly fractional, dynamic capital)

`src/trading/position_sizing.py`. Capital base = **live `NetLiquidation`**
(decision #1), clamped so a mis-read or a funded account can't distort sizing:

```
effective_capital = max(min(NetLiquidation, 2_000_000), 50_000)
kelly_raw  = (p*er - (1-p)*0.15) / er            # er = spread, 0.15 = avg break loss
position_pct = clamp(kelly_raw * 0.15, 0, 0.12)  # fractional 15%, hard cap 12%
size_eur = position_pct * effective_capital      # min EUR1000, else no trade
```

Guardrails are **non-bypassable and applied last** (Finance-V4 lesson): max 12%
per position, min €1000, max 5 concurrent. `expected_return <= 0` ⇒ no trade.

Entry pricing (decision #3): FR/DE limit = `mid * (1 + 0.1%)`; IT limit =
`last * (1 + 0.4%)` (Borsa Italiana delayed feed has no bid/ask). Stop =
`entry * (1 - 10%)`; take-profit = the offer price.

## Safeguards

| Safeguard | Trigger | Effect |
|---|---|---|
| **Kill switch** | `data/kill_switch.flag` present (Discord `!stop`) | cycle halts before the next order |
| **Daily loss limit** | NetLiq ≤ −2% of the day's baseline | arms the kill switch + halts (auto-shutdown) |
| **Position cap** | 5 open positions | new entries refused |
| **Order cooldown** | < 60 min since last order | candidate skipped |
| **Ramp-up** | first 5 validated trades | each requires manual `approve <trade_id>` before sending |
| **Heartbeat** | every 4h | Discord "system alive" |

The kill switch is a **file** (gitignored `data/`) so it can be flipped without a
DB write and survives restarts. Ramp-up count, daily baseline, and last-order
timestamp live in `system_state` (migration 0013).

## Failure modes & recovery

| Failure | Behaviour |
|---|---|
| IBKR Gateway disconnect | `IbkrClient.reconnect()` — linear backoff, 3 attempts; cycle skips if still down |
| Discord webhook fails | logged only, **never blocks trading** (alerts are best-effort) |
| DB write fails | the `session.commit()` raises ⇒ order is **not** marked SUBMITTED; the trade stays PENDING and is retried idempotently next cycle |
| Order rejected by IBKR | trade → REJECTED + Discord alert, **no auto-retry** (manual review) |
| Ticker unresolved | trade → REJECTED (`ticker_unresolved`); add a mapping to `src/trading/ticker_mapping.json` |
| Duplicate submit (same `trade_id`) | no-op (idempotent); a second open trade on the same deal is skipped |

## Timezone / DST

The daily cron uses `next_paris_time(now, 9, "Europe/Paris")` — **DST-aware**:
9h Paris = **07:00 UTC in summer (CEST)**, **08:00 UTC in winter (CET)**. Never
hardcode a fixed offset. Spring-forward (late March) and fall-back (late October)
are covered by tests in `tests/trading/test_scheduler.py`.

## IBKR Gateway setup

1. Log in to **portal.interactivebrokers.com** with **paper** credentials;
   confirm the `DU…` account + balance.
2. Start **IB Gateway** (or TWS) for the paper account on port **7497**:
   API → ✅ *Enable ActiveX and Socket Clients*, ❌ *Read-Only API* OFF, add
   `127.0.0.1` to *Trusted IPs*. IBC + auto-restart recommended for automation.
3. Verify with `scripts/ibkr_preflight.py` (see `docs/phase-08/ibkr-pre-flight.md`).

Config lives in `.env` / `Settings`: `IBKR_HOST/PORT/CLIENT_ID/PAPER`,
`DISCORD_WEBHOOK_ALERTS/DIGEST`, and the `TRADING_*` tunables.

Market data is **delayed (free, type 3)** for V1 (decision #2) — sufficient for a
daily cron. Real-time Euronext/Borsa/Xetra subscriptions are deferred (Phase 10+).

## Relationship: `trades` vs `paper_positions`

- **`trades`** (migration 0012) — the order-execution ledger: one row per
  submitted order, status machine PENDING → SUBMITTED → FILLED / REJECTED /
  CANCELLED, `trade_id` UNIQUE for idempotency.
- **`paper_positions`** (migration 0002) — current position state. On a BUY fill
  the executor opens/averages a position; on a SELL fill it closes it and writes
  realised P&L. The dashboard's Paper Portfolio page reads both, read-only.

## Lessons learned (carried from Finance-V4)

- **Server-side OCA brackets** — the stop is attached at entry and runs at native
  IBKR speed. FV4's audit attributed **78% of historical drawdown to stop
  slippage** from polling-based exits; this design removes that class of loss
  (gap risk remains).
- **Idempotency via `trade_id` UUID** — retry-safe submission; the same request
  never double-executes.
- **Logging hardening** — structured logs (structlog) never include the account
  id, IBKR credentials, or Discord tokens; Discord alerts are credential-free.

## Tech debt (accepted)

- Delayed market data (15-min) — realtime subscription deferred to Phase 10+.
- Borsa Italiana (IT) has no delayed bid/ask — IT entry uses `last + 0.4%`;
  subscription deferred to Phase 10+.
- Sanofi/SAN and other unresolved tickers — extend `ticker_mapping.json`.
- Order-id contiguity (`next_order_id` base / +1 / +2) is validated in the
  Step-11 live run; switch to place-parent-then-capture-id if IBKR rejects.
