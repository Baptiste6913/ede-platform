"""Tests for src.ingestion.consob.scrapingbee_client — budget + alerts."""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.exceptions import ExternalServiceError
from src.core.models import VendorApiUsage
from src.ingestion.consob.scrapingbee_client import (
    ScrapingBeeBudgetExceeded,
    ScrapingBeeClient,
)

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.integration


def _mock_transport(
    spb_cost: int,
    status_code: int = 200,
    body: str = '<ul class="consobResult"><li>ok</li></ul>',
) -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            text=body,
            headers={
                "Spb-Cost": str(spb_cost),
                "Spb-Initial-Status-Code": "200",
                "Spb-Resolved-Url": req.url.params.get("url", ""),
            },
        )

    return httpx.MockTransport(handler)


async def test_get_records_usage_row_with_correct_cost(
    db_engine: object,
    db_clean: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")
    from src.core.settings import get_settings

    get_settings.cache_clear()

    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    http = httpx.AsyncClient(transport=_mock_transport(spb_cost=1))
    client = ScrapingBeeClient(sf, http_client=http)

    resp = await client.get("https://www.consob.it/web/area-pubblica/documenti-opa")
    assert resp.credits_cost == 1
    assert resp.status_code == 200
    await client.aclose()

    async with sf() as s:
        rows = (await s.execute(select(VendorApiUsage))).scalars().all()
        assert len(rows) == 1
        assert rows[0].vendor == "scrapingbee"
        assert rows[0].credits_cost == 1
        assert rows[0].http_status == 200


async def test_get_refuses_when_monthly_budget_exhausted(
    db_engine: object,
    db_clean: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")
    monkeypatch.setenv("SCRAPINGBEE_MONTHLY_BUDGET", "10")
    from src.core.settings import get_settings

    get_settings.cache_clear()

    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    # Seed: 10 credits already consumed this month.
    from datetime import datetime

    ym = datetime.now(tz=UTC).strftime("%Y-%m")
    async with sf() as s:
        s.add(
            VendorApiUsage(
                vendor="scrapingbee",
                year_month=ym,
                request_url="x",
                target_url="x",
                credits_cost=10,
                http_status=200,
            )
        )
        await s.commit()

    http = httpx.AsyncClient(transport=_mock_transport(spb_cost=1))
    client = ScrapingBeeClient(sf, http_client=http)
    with pytest.raises(ScrapingBeeBudgetExceeded):
        await client.get("https://www.consob.it/web/area-pubblica/documenti-opa")
    await client.aclose()


async def test_alert_hook_fires_when_threshold_crossed(
    db_engine: object,
    db_clean: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")
    monkeypatch.setenv("SCRAPINGBEE_MONTHLY_BUDGET", "100")
    monkeypatch.setenv("SCRAPINGBEE_ALERT_THRESHOLDS", "50,75,90")
    from src.core.settings import get_settings

    get_settings.cache_clear()

    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    # Seed at 48% so a 5-credit call lands in the 50% threshold.
    from datetime import datetime

    ym = datetime.now(tz=UTC).strftime("%Y-%m")
    async with sf() as s:
        s.add(
            VendorApiUsage(
                vendor="scrapingbee",
                year_month=ym,
                request_url="x",
                target_url="x",
                credits_cost=48,
                http_status=200,
            )
        )
        await s.commit()

    alerts: list[str] = []

    async def _alert_hook(msg: str) -> None:
        alerts.append(msg)

    http = httpx.AsyncClient(transport=_mock_transport(spb_cost=5))
    client = ScrapingBeeClient(sf, http_client=http, alert_hook=_alert_hook)
    await client.get("https://www.consob.it/")
    await client.aclose()

    assert len(alerts) == 1
    assert "50%" in alerts[0]
    assert "53/100" in alerts[0]


async def test_get_raises_external_service_error_on_5xx(
    db_engine: object,
    db_clean: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")
    from src.core.settings import get_settings

    get_settings.cache_clear()

    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    http = httpx.AsyncClient(transport=_mock_transport(spb_cost=1, status_code=503))
    client = ScrapingBeeClient(sf, http_client=http)
    with pytest.raises(ExternalServiceError):
        await client.get("https://www.consob.it/")
    await client.aclose()

    # Usage row IS still recorded (we want to count failed calls against budget).
    async with sf() as s:
        count = await s.scalar(select(func.count()).select_from(VendorApiUsage))
        assert count == 1


async def test_used_credits_this_month_sums_current_period_only(
    db_engine: object,
    db_clean: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")
    from src.core.settings import get_settings

    get_settings.cache_clear()
    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]

    from datetime import datetime

    ym = datetime.now(tz=UTC).strftime("%Y-%m")
    async with sf() as s:
        s.add_all(
            [
                VendorApiUsage(
                    vendor="scrapingbee",
                    year_month=ym,
                    credits_cost=12,
                    http_status=200,
                ),
                VendorApiUsage(
                    vendor="scrapingbee",
                    year_month="1999-01",  # previous period — must be ignored
                    credits_cost=999,
                    http_status=200,
                ),
                VendorApiUsage(
                    vendor="other_vendor",
                    year_month=ym,
                    credits_cost=42,
                    http_status=200,
                ),
            ]
        )
        await s.commit()

    http = httpx.AsyncClient(transport=_mock_transport(spb_cost=1))
    client = ScrapingBeeClient(sf, http_client=http)
    used = await client.used_credits_this_month()
    await client.aclose()
    assert used == 12  # only scrapingbee + current month


async def test_get_builds_cheap_config_query_params(
    db_engine: object,
    db_clean: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default cheap config sends render_js=false and no premium_proxy."""
    _ = db_clean
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "k")
    monkeypatch.setenv("SCRAPINGBEE_RENDER_JS", "false")
    monkeypatch.setenv("SCRAPINGBEE_PREMIUM_PROXY", "false")
    from src.core.settings import get_settings

    get_settings.cache_clear()

    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.update(req.url.params)
        return httpx.Response(200, text="ok", headers={"Spb-Cost": "1"})

    sf = async_sessionmaker(db_engine, expire_on_commit=False)  # type: ignore[arg-type]
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = ScrapingBeeClient(sf, http_client=http)
    await client.get("https://www.consob.it/whatever")
    await client.aclose()

    assert captured["url"] == "https://www.consob.it/whatever"
    assert captured["api_key"] == "k"
    assert captured["render_js"] == "false"
    assert "premium_proxy" not in captured
