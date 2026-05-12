"""Typed exception hierarchy for EDE.

All raised application errors must subclass `EDEError`. Bare `except:` and
generic `except Exception:` are forbidden by CLAUDE.md section 4.
"""

from __future__ import annotations


class EDEError(Exception):
    """Base class for all EDE platform errors."""


class ConfigurationError(EDEError):
    """Raised when required configuration is missing or invalid."""


class DatabaseError(EDEError):
    """Raised on database connection or persistence failures."""


class ExternalServiceError(EDEError):
    """Raised when an upstream service (AMF, Consob, BaFin, IBKR, ...) fails."""

    def __init__(self, service: str, message: str, *, status_code: int | None = None) -> None:
        self.service = service
        self.status_code = status_code
        super().__init__(f"[{service}] {message}")


class RateLimitError(ExternalServiceError):
    """Raised when an upstream rate limit is hit."""


class NotFoundError(EDEError):
    """Raised when a domain object is not found."""
