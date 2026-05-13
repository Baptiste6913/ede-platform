"""AMF (Autorité des Marchés Financiers) poller — phase 2.

Public surface:

- `AmfPoller` — the orchestrator. `await poller.run_once()` polls RSS, fetches
  any new BDIF PDFs, parses metadata, and upserts into the `deals` table.
- `start_scheduled_poller(...)` — wire the poller into APScheduler with the
  configured interval.

Submodule responsibilities:

- `rate_limiter` — async token-bucket-ish limiter (1 req/s + jitter +
  exponential backoff on 429/503).
- `rss_watcher` — fetch the AMF RSS feed and filter for M&A-related items.
- `bdif_fetcher` — locate and download BDIF PDFs with atomic write.
- `parser` — extract `regulator_ref`, `deal_type`, target/acquirer names,
  dates, etc., from the RSS title and the first 5 PDF pages.
- `service` — dedup on (`juridiction='FR'`, `regulator_ref`) and persist.
"""

from src.ingestion.amf.poller import AmfPoller, start_scheduled_poller

__all__ = ["AmfPoller", "start_scheduled_poller"]
