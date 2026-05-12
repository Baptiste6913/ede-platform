"""Health and readiness endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

from src.core import db, get_settings

router = APIRouter(tags=["health"])

_START_TS = time.monotonic()


class DBHealth(BaseModel):
    ok: bool
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    db: DBHealth


@router.get("/health", response_model=HealthResponse, summary="Service health")
async def health() -> HealthResponse:
    """Return service status, version, uptime, and DB connectivity."""
    settings = get_settings()
    db_status = await db.ping()
    status = "ok" if db_status.get("ok") else "degraded"
    return HealthResponse(
        status=status,
        version=settings.app_version,
        uptime_seconds=round(time.monotonic() - _START_TS, 2),
        db=DBHealth(**db_status),
    )
