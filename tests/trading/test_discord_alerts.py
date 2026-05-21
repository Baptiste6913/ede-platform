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
