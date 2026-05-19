"""BaFin (DE) poller — phase 5.

Architecture (post Step-0 finding — no anti-bot):
- Listing page (monolithic, ~241 rows, no pagination) → plain httpx, 0 credits.
- PDF download URL is **deterministic** from each wrapper URL:
  `…/{slug}.html?nn=…` → `…/{slug}.pdf?__blob=publicationFile&v=1`.
  We skip the wrapper fetch in the happy path; fall back to scraping
  the wrapper only when the deterministic PDF URL 404s.

Public surface:
- `BafinPoller` — orchestrator with run_backfill() / run_incremental().
- `BafinDiscoveryClient` — parses the listing, yields `AngebotsunterlageRecord`.
- `BafinPdfFetcher` — plain httpx download with atomic write.
"""

from src.ingestion.bafin.discovery import (
    AngebotsunterlageRecord,
    BafinDiscoveryClient,
)
from src.ingestion.bafin.fetcher import BafinPdfFetcher
from src.ingestion.bafin.poller import BafinPoller

__all__ = [
    "AngebotsunterlageRecord",
    "BafinDiscoveryClient",
    "BafinPdfFetcher",
    "BafinPoller",
]
