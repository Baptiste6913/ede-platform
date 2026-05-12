"""Tests for src.core.exceptions."""

from __future__ import annotations

import pytest

from src.core.exceptions import (
    DatabaseError,
    EDEError,
    ExternalServiceError,
    RateLimitError,
)


def test_database_error_is_ede_error() -> None:
    with pytest.raises(EDEError):
        raise DatabaseError("boom")


def test_external_service_error_carries_service_and_status() -> None:
    exc = ExternalServiceError("amf", "timeout", status_code=504)
    assert exc.service == "amf"
    assert exc.status_code == 504
    assert "[amf]" in str(exc)


def test_rate_limit_is_external() -> None:
    exc = RateLimitError("consob", "429")
    assert isinstance(exc, ExternalServiceError)
    assert isinstance(exc, EDEError)
