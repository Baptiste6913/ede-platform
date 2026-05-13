"""AMF RSS watcher.

Fetches https://www.amf-france.org/fr/flux-rss/display/23 and filters items
matching the M&A regex from CLAUDE.md §7 phase 2 + this phase's brief:

    (offre publique | garantie de cours | note d'information
     | OPA | OPE | OPRA | OPR)

Returns a list of `RssItem` ready for downstream BDIF fetching + parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final

import feedparser
import httpx
import structlog

from src.core.settings import get_settings
from src.ingestion.amf.rate_limiter import RateLimiter, retry_with_backoff

_log = structlog.get_logger(__name__)

# Case-insensitive regex over each RSS entry's title (+ summary as fallback).
TITLE_REGEX: Final[re.Pattern[str]] = re.compile(
    r"(offre publique|garantie de cours|note d'information|OPA|OPE|OPRA|OPR)",
    re.IGNORECASE,
)

# Extract a regulator reference of the form AMF-YYYY-X-NNNN from titles/links.
# AMF references seen: AMF-YYYY-C-NNNN, AMF-YYYY-D-NNNN, AMF-YYYY-E-NNNN,
# AMF-YYYY-S-NNNN. We accept any single uppercase letter as category.
_REGREF_REGEX: Final[re.Pattern[str]] = re.compile(r"\bAMF-\d{4}-[A-Z]-\d{3,5}\b")


@dataclass(frozen=True, slots=True)
class RssItem:
    """A filtered RSS entry — the input to the BDIF fetcher."""

    title: str
    link: str
    summary: str
    published: datetime | None
    regulator_ref: str | None

    @property
    def published_date(self) -> date | None:
        return self.published.date() if self.published else None


class RssWatcher:
    """Polls the AMF RSS feed and yields filtered items."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        rate_limiter: RateLimiter,
        *,
        url: str | None = None,
        max_retries: int | None = None,
    ) -> None:
        settings = get_settings()
        self._client = client
        self._rate_limiter = rate_limiter
        self._url = url or settings.amf_rss_url
        self._max_retries = (
            max_retries if max_retries is not None else settings.poller_amf_max_retries
        )

    async def fetch(self) -> list[RssItem]:
        """Fetch + parse + filter the RSS feed. Returns matching items only."""
        await self._rate_limiter.acquire()
        body = await retry_with_backoff(
            self._get_body,
            max_retries=self._max_retries,
            service="amf-rss",
        )
        return self._parse(body)

    async def _get_body(self) -> bytes:
        resp = await self._client.get(self._url)
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def _parse(body: bytes) -> list[RssItem]:
        feed = feedparser.parse(body)
        items: list[RssItem] = []
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or "").strip()
            link = (entry.get("link") or "").strip()
            haystack = f"{title}\n{summary}"
            if not TITLE_REGEX.search(haystack):
                continue
            published = _parse_published(entry)
            regulator_ref = _extract_regulator_ref(title, link, summary)
            items.append(
                RssItem(
                    title=title,
                    link=link,
                    summary=summary,
                    published=published,
                    regulator_ref=regulator_ref,
                )
            )
        _log.info(
            "amf.rss.fetched",
            total=len(feed.entries),
            matched=len(items),
        )
        return items


def _parse_published(entry: feedparser.FeedParserDict) -> datetime | None:
    """Try `published_parsed`, then `updated_parsed`. Returns timezone-aware UTC."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    # parsed is a time.struct_time. Index explicitly to keep mypy happy
    # (datetime(*tuple, tzinfo=...) confuses the type checker).
    return datetime(
        parsed[0],
        parsed[1],
        parsed[2],
        parsed[3],
        parsed[4],
        parsed[5],
        tzinfo=UTC,
    )


def _extract_regulator_ref(title: str, link: str, summary: str) -> str | None:
    """Search title, link, then summary for the canonical AMF reference."""
    for source in (title, link, summary):
        if not source:
            continue
        m = _REGREF_REGEX.search(source)
        if m:
            return m.group(0)
    return None
