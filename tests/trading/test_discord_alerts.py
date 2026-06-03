"""Unit tests for Discord alerts (captured posts, no network) + command parsing."""

from __future__ import annotations

import pytest

from src.trading.discord_alerts import DiscordAlerts, parse_command


class Capture:
    def __init__(self):
        self.posts = []

    async def __call__(self, url, payload):
        self.posts.append((url, payload["content"]))


def _alerts(cap):
    return DiscordAlerts(webhook_alerts="http://a", webhook_digest="http://d", post_fn=cap)


async def test_disabled_when_no_webhook():
    cap = Capture()
    alerts = DiscordAlerts(webhook_alerts="", post_fn=cap)
    assert alerts.enabled is False
    await alerts.trade_submitted("Deal", 10, 9.0)
    assert cap.posts == []  # no-op


async def test_trade_generated_mentions_rampup():
    cap = Capture()
    await _alerts(cap).trade_generated("Commerzbank", 100, 23.75, 2, 5)
    url, content = cap.posts[0]
    assert url == "http://a"
    assert "ramp-up 2/5" in content and "Commerzbank" in content and "100" in content


async def test_lifecycle_alerts_go_to_alerts_webhook():
    cap = Capture()
    a = _alerts(cap)
    await a.trade_submitted("D", 10, 9.0)
    await a.trade_filled("D", 9.0, 0.95)
    await a.trade_rejected("D", "ticker_unresolved")
    await a.stop_hit("D", -120.0)
    await a.profit_taken("D", 340.0)
    await a.heartbeat(3, 0.012)
    await a.kill_switch_active()
    await a.daily_loss_limit(0.02)
    assert all(url == "http://a" for url, _ in cap.posts)
    joined = " ".join(c for _, c in cap.posts)
    assert "📤" in joined and "✅" in joined and "❌" in joined
    assert "🛑" in joined and "💰" in joined and "🚨" in joined


async def test_daily_pnl_goes_to_digest():
    cap = Capture()
    await _alerts(cap).daily_pnl(1_002_000, 0.0022, 3)
    url, content = cap.posts[0]
    assert url == "http://d"
    assert "Daily P&L" in content and "3 positions" in content


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("!stop", ("stop", None)),
        ("stop", ("stop", None)),
        ("!status", ("status", None)),
        ("approve abc-123", ("approve", "abc-123")),
        ("!approve  abc-123", ("approve", "abc-123")),
        ("hello", None),
        ("approve", None),
        ("approve a b", None),
    ],
)
def test_parse_command(text, expected):
    assert parse_command(text) == expected


async def test_alerts_never_raise_on_post_failure():
    # Default httpx path must swallow connection errors (alerting never breaks trading).
    alerts = DiscordAlerts(webhook_alerts="http://127.0.0.1:1/none")
    await alerts.trade_submitted("D", 1, 1.0)  # must not raise


# --------------------------------------------------- decision embed (Phase 13)
class CaptureRaw:
    def __init__(self):
        self.posts = []

    async def __call__(self, url, payload):
        self.posts.append((url, payload))


def _req(**kw):
    from src.trading.decision_engine import TradeRequest

    base = {
        "trade_id": "t1",
        "deal_id": 7,
        "deal_target": "Covivio Hotels",
        "deal_acquirer": "Covivio SA",
        "side": "BUY",
        "quantity": 120,
        "symbol": "COVH",
        "exchange": "SBF",
        "isin": "FR0000060303",
        "currency": "EUR",
        "limit_price": 50.05,
        "stop_loss_price": 45.05,
        "take_profit_price": 52.0,
        "expected_p_completion": 0.92,
        "expected_return_pct": 0.039,
        "kelly_fractional_pct": 0.08,
        "position_pct": 0.06,
        "rationale": "r",
        "requires_approval": False,
        "score_stars": 4,
    }
    base.update(kw)
    return TradeRequest(**base)


def _deal(**kw):
    from datetime import date
    from decimal import Decimal
    from types import SimpleNamespace

    base = {
        "target_name": "Covivio Hotels",
        "juridiction": "FR",
        "ticker_target": "FR0000060303",
        "trading_ticker_yf": "COVH.PA",
        "ibkr_ticker": "COVH",
        "ibkr_exchange": "SBF",
        "offer_price": Decimal("52.0"),
        "reference_price_at_announcement": Decimal("50.0"),
        "premium_pct": Decimal("0.0400"),
        "deal_type": "opa",
        "payment_cash_share": Decimal("1.0"),
        "regulator_ref": "224C0763",
        "source_url": "https://amf-france.org/224C0763",
        "announcement_date": date(2026, 5, 20),
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _embed(posts):
    url, payload = posts[0]
    return url, payload["embeds"][0]


async def test_decision_alert_embed_has_critical_fields():
    cap = CaptureRaw()
    await _alerts(cap).decision_alert(_req(), _deal())
    url, embed = _embed(cap.posts)
    assert url == "http://a"
    assert embed["title"] == "🟢 ACHAT — Covivio Hotels (FR)"
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["Ticker IBKR"] == "COVH @ SBF"
    assert fields["Ticker yfinance"] == "COVH.PA"
    assert fields["Entry / Stop / TP"] == "50.05 / 45.05 / 52.00 EUR"
    assert fields["Score"] == "4/5 (p=92%)"
    assert fields["Premium"] == "4.0%"
    assert "Merger arb" in fields["Stratégie"]
    assert "224C0763" in embed["footer"]["text"]


async def test_decision_alert_premium_null_na():
    cap = CaptureRaw()
    await _alerts(cap).decision_alert(_req(), _deal(premium_pct=None))
    _, embed = _embed(cap.posts)
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["Premium"] == "N/A"  # graceful, no crash


async def test_decision_alert_no_ibkr_ticker_falls_back_to_isin():
    cap = CaptureRaw()
    await _alerts(cap).decision_alert(_req(), _deal(ibkr_ticker=None, ibkr_exchange=None))
    _, embed = _embed(cap.posts)
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["Ticker IBKR"] == "via ISIN FR0000060303"


async def test_decision_alert_no_op_when_disabled():
    cap = CaptureRaw()
    alerts = DiscordAlerts(webhook_alerts="", post_fn=cap)
    await alerts.decision_alert(_req(), _deal())
    assert cap.posts == []  # no webhook ⇒ no-op
