# Phase 8 — Step 0: IBKR pre-flight

**Status: ✅ DONE (with 3 decisions to confirm before Steps 1-12).** Live run 2026-05-21 against IB Gateway paper on `127.0.0.1:7497`. Branch `phase-08-paper-trading-ibkr`. Tool: `scripts/ibkr_preflight.py` (read-only, places no orders).

> Security: account id is **redacted** here (paper `DU…` prefix confirmed). No IBKR secret / Finance-V4 `.env` value appears in this file.

## Environment recon

| Check | Result |
|---|---|
| `ib_async` | installed **2.1.0** in `.venv` (pyproject add deferred to Step 1). |
| IBKR config (`settings.py` + `.env`) | ✅ flat fields `ibkr_host=127.0.0.1`, `ibkr_port=7497`, `ibkr_client_id=42`, `ibkr_paper=true`. |
| Discord config | ✅ `DISCORD_WEBHOOK_ALERTS` + `DISCORD_WEBHOOK_DIGEST` present. |
| Finance-V4 reuse | mapped in `artifacts/phase-08/finance-v4-reuse-map.md` (same `ib_async`/`structlog` stack). |
| Paper guard | ✅ script aborts unless `ibkr_paper=true` AND port ∈ {7497,4002}; asserts `DU…` account. |

## Live results

### [1] Connection ✅
- Connect latency: **~120 ms** warm (626 ms on the first cold connect of the session).
- `disconnectedEvent` wired; auto-reconnect pattern available (ported from Finance-V4 in Step 1).

### [2] Account ✅ (paper confirmed)
- Account: **`DU…`** paper account (prefix verified — redacted). A pseudo-account `All` (aggregate) also returned by `accountSummary` → filter to `DU…` accounts in code.
- NetLiquidation: **≈ €1,002,755** · TotalCash ≈ €1,002,031.
- ⚠️ **Balance is ~1M EUR, not the ~100k assumed in the brief.** → decision #1 below.

### [3] Timezone ✅
- IBKR server time returned in **UTC**; local machine **Europe/Paris CEST (UTC+2, DST active — "heure d'été")**; skew ≈ +1 s.
- Implication: store/compare everything in **UTC**; the **9h Paris cron must use the `Europe/Paris` tz (DST-aware)** = 07:00 UTC in summer, 08:00 UTC in winter. Do **not** hardcode a fixed UTC offset.

### [4] Market data + asset coverage — 5/6 qualified
Markets were closed (run at 18:13 CEST). Snapshot via **delayed feed (`reqMarketDataType(3)`, free tier)**:

| Ticker | Exchange | Qualified | conId | Delayed data |
|---|---|---|---|---|
| Airbus (AIR) | FR / Euronext Paris (SBF) | ✅ | 29612256 | bid 166.82 / ask 166.94 / last 166.94 / close 173.36 |
| Sanofi (SAN) | FR / Euronext Paris (SBF) | ❌ | — | **Error 200 — no security definition** |
| Enel (ENEL) | IT / Borsa Italiana (BVME) | ✅ | 29816333 | last 9.765 / close 9.669 · **no bid/ask (−1)** |
| Eni (ENI) | IT / Borsa Italiana (BVME) | ✅ | 29816844 | last 23.79 / close 23.54 · **no bid/ask (−1)** |
| SAP (SAP) | DE / Xetra (IBIS) | ✅ | 14204 | bid 151.08 / ask 151.26 / last 151.46 / close 153.42 |
| BASF (BAS) | DE / Xetra (IBIS) | ✅ | 77680640 | bid 51.85 / ask 51.92 / last 51.92 / close 51.10 |

**Market-data permissions (key finding):**
- **Realtime is NOT subscribed** — `reqMarketDataType(1)` returned **Error 354 "market data not subscribed"** for SBF & IBIS (all NaN).
- **Delayed (free) works on all 3 exchanges** — FR & DE return full bid/ask/last/close; **IT (BVME) returns last/close only, no bid/ask**.
- For a **daily 9h merger-arb cron, delayed is sufficient**. IT spread/limit pricing must fall back to **last/close** (no bid/ask on BVME delayed).

**Coverage:** 5/6. Sanofi failed (symbol/listing nuance — AIR qualifies on the *same* SBF, so the FR exchange itself is fine). Defer to the Step 2 ticker resolver (likely a `localSymbol`/ISIN qualification, not "SAN" on SMART/SBF).

## Warnings encountered
- `Error 200` — Sanofi `SAN` not found on SBF/SMART (symbol mapping, Step 2).
- `Error 354` — realtime market data not subscribed (SBF, IBIS) → using delayed.
- `accountSummary` returns an extra `All` aggregate row → filter to `DU…`.
- Windows console is cp1252 → script forces UTF-8 stdout (handled).

## ▶️ Decisions to confirm before Steps 1-12

1. **Capital base.** Paper account holds **~€1M**, brief sizing assumes **€100k**. Options:
   (a) Reset paper account to 100k (Settings → Reset Paper Account), or
   (b) **[recommended]** size off **live `NetLiquidation`** dynamically (more robust; max-12%/Kelly scale to real equity) and drop the hardcoded 100k.
2. **Market data tier.** Accept **delayed (free)** for V1 (fine for a daily cron), or subscribe **realtime** Euronext/Borsa/Xetra bundles (paid) for tighter entry pricing? Recommended: delayed for V1, revisit at scale.
3. **IT bid/ask gap.** BVME delayed has **no bid/ask** → limit-order entry price for IT deals derived from **last/close + offset**. Confirm acceptable.

(Sanofi mapping is not a blocker — handled by the Step 2 ticker resolver.)

**Acceptance vs brief:** connection ✅ · paper balance confirmed ✅ (but ~1M, see #1) · 5/6 sample contracts qualified (Sanofi deferred). → **STOP for user validation before architecture coding (Steps 1-12).**
