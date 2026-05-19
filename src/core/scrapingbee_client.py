"""ScrapingBee client with monthly-budget enforcement.

Wraps `httpx` against `https://app.scrapingbee.com/api/v1/` and persists
a per-call usage row in the `vendor_api_usage` table. Refuses new calls
once monthly consumption crosses the configured hard limit (default 900
on a 1000-credit Free Tier, leaving 100 credits as headroom for the
first incremental polls of the following month).

Discord alerts (phase 11) are emitted via a callable hook when usage %
crosses each configured threshold (50, 75, 90).

Empirically (2026-05-19) the cheapest viable config for Consob's
documenti-opa listing is `render_js=false, premium_proxy=false` at
1 credit / call. PDFs are NOT Radware-protected and download via the
sibling `ConsobPdfFetcher` for 0 credits.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from sqlalchemy import func, select

from src.core.exceptions import EDEError, ExternalServiceError
from src.core.models import VendorApiUsage
from src.core.settings import get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)

VENDOR = "scrapingbee"
HTTP_CLIENT_ERROR_THRESHOLD = 400


class ScrapingBeeBudgetExceeded(EDEError):  # noqa: N818 — exception name matches public API used in tests
    """Raised when the next ScrapingBee call would push monthly usage
    past `scrapingbee_monthly_budget`."""

    def __init__(self, used: int, budget: int, requested_cost: int) -> None:
        self.used = used
        self.budget = budget
        self.requested_cost = requested_cost
        super().__init__(
            f"ScrapingBee monthly budget exceeded: used={used} budget={budget} "
            f"requested={requested_cost}",
        )


@dataclass(frozen=True, slots=True)
class ScrapingBeeResponse:
    """Outcome of a `ScrapingBeeClient.get()` call."""

    status_code: int
    text: str
    content: bytes
    credits_cost: int
    target_url: str


AlertHook = Callable[[str], Awaitable[None]]


class ScrapingBeeClient:
    """Async, budget-aware ScrapingBee client.

    Each call:
      1. counts current month's spend from `vendor_api_usage`
      2. raises `ScrapingBeeBudgetExceeded` if the *configured cap* would
         be crossed (we count cost AFTER the call from the `Spb-Cost`
         header; on the first call of a new month a single over-budget
         call is still allowed because we cannot know the cost upfront)
      3. issues the GET to ScrapingBee
      4. inserts a `VendorApiUsage` row
      5. fires Discord alerts on threshold crossings
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        http_client: httpx.AsyncClient | None = None,
        alert_hook: AlertHook | None = None,
    ) -> None:
        settings = get_settings()
        self._session_factory = session_factory
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.scrapingbee_timeout_seconds),
        )
        self._alert_hook = alert_hook
        self._key = settings.scrapingbee_api_key.get_secret_value()
        self._base_url = settings.scrapingbee_base_url
        self._budget = settings.scrapingbee_monthly_budget
        self._render_js = settings.scrapingbee_render_js
        self._premium = settings.scrapingbee_premium_proxy
        self._country = settings.scrapingbee_country_code
        self._thresholds = settings.scrapingbee_alert_threshold_pcts

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def used_credits_this_month(self) -> int:
        """Sum of `credits_cost` for the current YYYY-MM."""
        ym = _current_year_month()
        async with self._session_factory() as session:
            value = await session.scalar(
                select(func.coalesce(func.sum(VendorApiUsage.credits_cost), 0)).where(
                    VendorApiUsage.vendor == VENDOR,
                    VendorApiUsage.year_month == ym,
                )
            )
        return int(value or 0)

    async def get(self, target_url: str, **overrides: Any) -> ScrapingBeeResponse:
        """Fetch `target_url` through ScrapingBee. Respects budget.

        `overrides` accept `render_js`, `premium_proxy`, `country_code`
        as booleans / strings to escalate from the default cheap config.
        """
        used = await self.used_credits_this_month()
        if used >= self._budget:
            raise ScrapingBeeBudgetExceeded(used=used, budget=self._budget, requested_cost=1)

        params: dict[str, str] = {
            "api_key": self._key,
            "url": target_url,
        }
        render_js = bool(overrides.get("render_js", self._render_js))
        premium = bool(overrides.get("premium_proxy", self._premium))
        country = overrides.get("country_code", self._country)
        if render_js:
            params["render_js"] = "true"
        else:
            params["render_js"] = "false"
        if premium:
            params["premium_proxy"] = "true"
            if country:
                params["country_code"] = str(country)

        resp = await self._client.get(self._base_url, params=params)
        cost = int(resp.headers.get("Spb-Cost", "1"))

        await self._record_usage(
            target_url=target_url,
            credits_cost=cost,
            http_status=resp.status_code,
            extra={
                "render_js": render_js,
                "premium_proxy": premium,
                "country_code": country if premium else None,
                "spb_initial_status_code": resp.headers.get("Spb-Initial-Status-Code"),
                "spb_resolved_url": resp.headers.get("Spb-Resolved-Url"),
            },
        )

        new_used = used + cost
        await self._maybe_alert(used_before=used, used_after=new_used)

        if resp.status_code >= HTTP_CLIENT_ERROR_THRESHOLD:
            raise ExternalServiceError(
                "scrapingbee",
                f"non-2xx from ScrapingBee: {resp.status_code}",
                status_code=resp.status_code,
            )

        return ScrapingBeeResponse(
            status_code=resp.status_code,
            text=resp.text,
            content=resp.content,
            credits_cost=cost,
            target_url=target_url,
        )

    async def _record_usage(
        self,
        *,
        target_url: str,
        credits_cost: int,
        http_status: int,
        extra: dict[str, Any],
    ) -> None:
        ym = _current_year_month()
        async with self._session_factory() as session:
            session.add(
                VendorApiUsage(
                    vendor=VENDOR,
                    year_month=ym,
                    request_url=self._base_url,
                    target_url=target_url,
                    credits_cost=credits_cost,
                    http_status=http_status,
                    extra=extra,
                )
            )
            await session.commit()

    async def _maybe_alert(self, *, used_before: int, used_after: int) -> None:
        if self._alert_hook is None:
            return
        if self._budget <= 0:
            return
        pct_before = (used_before * 100) // self._budget
        pct_after = (used_after * 100) // self._budget
        for threshold in self._thresholds:
            if pct_before < threshold <= pct_after:
                msg = (
                    f"ScrapingBee monthly usage crossed {threshold}% "
                    f"({used_after}/{self._budget} credits)"
                )
                _log.warning("consob.scrapingbee.alert", threshold=threshold, used=used_after)
                await self._alert_hook(msg)


def _current_year_month() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m")
