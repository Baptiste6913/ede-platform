# Phase 8 — Finance-V4 → EDE reuse map

Source archive moved to `C:\Users\bapti\Code\finance-v4` (kept its own `.git`; **no** new `git init` done — history preserved). Analysis is read-only; **no code copied yet** (that happens per-step during architecture). Finance-V4 uses the same broker lib (`ib_async`) and `structlog`, so the execution layer ports cleanly. Key structural diffs to bridge: Finance-V4 is **US equities/options, USD, intraday catalyst trading**; EDE is **EU equities (FR/IT/DE), EUR, daily M&A merger-arb, long-only**.

## Reuse table

| Source file (Finance-V4) | Lines | Purpose | Reuse strategy EDE | Target EDE file |
|---|---|---|---|---|
| `src/execution/ibkr_client.py` | 366 | IBKR wrapper: `connect`/`reconnect` (backoff)/`disconnectedEvent`/`is_connected`/`get_snapshot`/tolerant per-contract qualify | **Adapt** — keep connection mgmt + auto-reconnect + the one-at-a-time qualify-tolerant pattern + snapshot; **drop** options & historical methods (guardrail: long equity only); USD→EUR; settings are **flat** in EDE (`settings.ibkr_host`) vs nested (`settings.ibkr.host`) | `src/trading/ibkr_client.py` (Step 1) |
| `src/execution/bracket_order_builder.py` | 249 | **Pure-function** 3-leg bracket: parent LMT/MKT + stop-loss + take-profit, OCA server-side, tick rounding, sanity guards | **Copy ≈ verbatim** — this *is* EDE's "limit entry + auto-attached stop + auto-attached TP" (Step 5 success criterion 4); EDE long-only ⇒ `Direction` always LONG; swap the `Direction/Side` import for EDE's enum | `src/trading/bracket_builder.py` + `executor.py` (Step 5) |
| `src/execution/risk_manager.py` | 107 | Position sizing with **non-bypassable guardrails applied LAST** (after any adjustment) + max-position cap | **Adapt** — keep the "guardrails always last + max cap + share calc" skeleton; **replace** the tier-risk formula with **Kelly fractional 15% / max 12% / min €1000** per brief | `src/trading/position_sizing.py` (Step 3) |
| `src/execution/order_manager.py` | 163 | Orchestration: resolve price → size → fill → register position → Discord notify; "skip if position already open"; correlation caps | **Adapt skeleton** — reuse the pipeline shape + the open-position skip + the notify hook; **drop** US `SECTOR_MAP` + catalyst correlation; EDE dedups on `cluster_id` + DB `trade_id` instead | `src/trading/decision_engine.py` + `executor.py` (Steps 4-5) |
| `src/execution/position_monitor.py` | 272 | Monitors open positions, stop/target hits, P&L; fires close notifications | **Adapt** — reuse the monitor loop + stop-hit detection feeding EDE's `STOP_HIT`/`PROFIT_TAKEN` alerts; back it with the DB `trades` table | `src/trading/scheduler.py` (monitor) + `executor.py` (Steps 5,8) |
| `src/notifications/discord_notifier.py` | 134 | Discord webhook via `httpx`, **never raises** (logs), `is_enabled` guard, embed builder + footer | **Copy + extend** — reuse `_post`/`is_enabled`/`_footer`/embed verbatim; extend to EDE's 10 alert types (GENERATED/SUBMITTED/FILLED/REJECTED/STOP_HIT/PROFIT/DAILY_PNL/HEARTBEAT/KILL_SWITCH/LOSS_LIMIT); EDE has **2** webhooks (`alerts` + `digest`) | `src/trading/discord_alerts.py` (Step 7) |
| `src/execution/paper_broker.py` | 151 | In-memory paper fill **simulation** | **Reference only** — EDE places **real** IBKR paper orders (`ib.placeOrder`), not simulated fills; not ported | — |
| `src/core/logger.py` | 33 | `structlog` setup (contextvars, ISO ts, JSON/console) | **Skip** — EDE already ships `src/core/logging.py`; reuse EDE's. Action: verify it redacts secrets (no webhook/token leak) | (EDE existing) |
| `src/models/trade.py` | 86 | `Position` dataclass | **Reference** — informs EDE's `TradeRequest`/`Position` shapes + `trades` table columns (migration 0012) | `src/trading/*` models (Step 5) |

## Cross-cutting patterns worth porting

- **Graceful degradation** (`ibkr_client`): every broker call is `try/except → log.warning + return empty/None`, never crashes the cycle. Adopt for all EDE IBKR calls.
- **Guardrails non-bypassable, applied last** (`risk_manager`): adjustments first, hard caps last. Map to EDE's Kelly + max-12% + max-5-positions + min-€1000.
- **Server-side brackets eliminate stop slippage** (`bracket_order_builder` docstring): Finance-V4 `AUDIT_FINAL.md` attributes **78% of historical drawdown to stop slippage** from polling-based exits. EDE must attach stop server-side at entry (transmit on last child), not poll — directly satisfies success criterion 4.
- **Discord never-raises** (`discord_notifier`): alerting failures must never break trading.

## New in EDE — no Finance-V4 reuse (build fresh)

- **DB-backed `trade_id` idempotency** (Step 5): Finance-V4 only dedups in-memory ("skip open position"). EDE needs the `trades` table UNIQUE(`trade_id`) check before submit (migration 0012).
- **Kill switch file** + Discord `!stop` (Step 6): not present in Finance-V4.
- **Ramp-up state** (first 5 trades manual) via `system_state` table (Step 6, migration 0013).
- **Daily loss limit −2% auto-shutdown**, **position cap 5**, **1h cooldown**, **4h heartbeat** (Step 6).
- **Ticker resolver** deals→IBKR contract by ISIN/manual map/fuzzy (Step 2): Finance-V4 loads a static universe; EDE resolves per-deal (migration 0011 adds `deals.ibkr_ticker`/`ibkr_exchange`).
- **Daily cron scheduler** 9h Paris (Step 8): Finance-V4 is event-bus/intraday driven.

## Notes / flags

- Finance-V4 `.env` (with secrets) is present in the archive — **not read**, will not be committed; EDE keeps its own `.env`.
- Finance-V4 config is split (`config/settings.py` → `RiskSettings`/`DiscordSettings`); EDE centralizes in `src/core/settings.py` (flat fields already scaffolded for IBKR + Discord).
- ib_async API parity confirmed: `connectAsync`, `qualifyContractsAsync`, `reqMktData`, `placeOrder`, `MarketOrder/StopOrder/LimitOrder` — all available in the `ib_async 2.1.0` installed in EDE's `.venv`.
