"""ASGI middlewares for the FastAPI app."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.logging import get_logger, set_correlation_id

_HEADER_NAME = "x-correlation-id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a correlation_id per request to structlog contextvars.

    Reads the inbound `X-Correlation-Id` header if present; otherwise generates
    a UUID4. Echoes the header on the response.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        cid = request.headers.get(_HEADER_NAME) or uuid.uuid4().hex
        set_correlation_id(cid)
        logger = get_logger("api.request")
        started = time.perf_counter()

        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            set_correlation_id(None)

        response.headers[_HEADER_NAME] = cid
        return response
