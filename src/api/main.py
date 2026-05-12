"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.middleware import CorrelationIdMiddleware
from src.api.routes_health import router as health_router
from src.core import configure_logging, db, get_logger, get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Configure logging on startup and dispose the DB engine on shutdown."""
    settings = get_settings()
    configure_logging(level=settings.log_level)
    log = get_logger("api.lifespan")
    log.info("startup", env=settings.env, version=settings.app_version)
    try:
        yield
    finally:
        await db.dispose_engine()
        log.info("shutdown")


def create_app() -> FastAPI:
    """Build the FastAPI app. Importable as `src.api.main:app`."""
    settings = get_settings()
    app = FastAPI(
        title="EDE Platform API",
        version=settings.app_version,
        description="Event-Driven Europe — M&A detection, scoring, paper trading.",
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health_router)
    return app


app = create_app()
