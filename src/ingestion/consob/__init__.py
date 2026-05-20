"""Consob (IT) poller — phase 4.

Architecture (post Step 0 anti-bot finding):
- Listing pages (Liferay portlet, Radware-protected) → ScrapingBee API
  with cheapest config (render_js=False, premium_proxy=False = 1 credit).
- PDFs (under /documents/, NOT Radware-protected) → plain httpx, 0 credits.

Public surface:
- `ConsobPoller` — orchestrator with run_backfill() / run_incremental().
- `ScrapingBeeClient` — budget-enforced HTTP client for the listing pages.
- `ConsobDiscoveryClient` — paginates the OPA listing, yields `OpaRecord`.
- `ConsobPdfFetcher` — plain httpx download with atomic write.
"""

from src.core.scrapingbee_client import (
    ScrapingBeeBudgetExceeded,
    ScrapingBeeClient,
)
from src.ingestion.consob.discovery import ConsobDiscoveryClient, OpaRecord
from src.ingestion.consob.fetcher import ConsobPdfFetcher
from src.ingestion.consob.poller import ConsobPoller

__all__ = [
    "ConsobDiscoveryClient",
    "ConsobPdfFetcher",
    "ConsobPoller",
    "OpaRecord",
    "ScrapingBeeBudgetExceeded",
    "ScrapingBeeClient",
]
