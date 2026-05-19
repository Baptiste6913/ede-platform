"""structlog JSON logging with correlation_id support.

Usage:
    from src.core.logging import configure_logging, get_logger

    configure_logging(level="INFO")
    log = get_logger(__name__)
    log.info("event", deal_id=123)

Correlation IDs are set per-request by `CorrelationIdMiddleware`. Library code
just calls `log.info(...)`; the contextvar is bound automatically.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any, cast

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.types import EventDict, Processor

_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_configured: bool = False


def _add_correlation_id(_: Any, __: str, event_dict: EventDict) -> EventDict:
    """Inject correlation_id from contextvar if present."""
    cid = _correlation_id_var.get()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to emit JSON to stdout. Idempotent."""
    global _configured  # noqa: PLW0603 — module-level singleton guard
    if _configured:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        _add_correlation_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Route everything through stdlib logging so `add_logger_name` works
    # (stdlib loggers have a `.name` attribute; PrintLogger doesn't).
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    # httpx INFO-level emits the full request URL (including query string with
    # api_key for ScrapingBee — confirmed leak in Phase-4 Step-9 live run).
    # Mute it at WARNING; our service-layer structlog calls already capture
    # the relevant fields (target_url, status, cost) without secrets.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to `name`."""
    if not _configured:
        configure_logging()
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))


def set_correlation_id(cid: str | None) -> None:
    """Set the correlation_id contextvar. None clears it."""
    _correlation_id_var.set(cid)
    if cid is None:
        clear_contextvars()
    else:
        bind_contextvars(correlation_id=cid)


def get_correlation_id() -> str | None:
    return _correlation_id_var.get()


def _reset_for_tests() -> None:
    """Reset module state. Test-only helper."""
    global _configured  # noqa: PLW0603
    _configured = False
    structlog.reset_defaults()
    clear_contextvars()
