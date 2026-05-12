"""Tests for src.core.logging."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from src.core.logging import (
    _reset_for_tests,
    configure_logging,
    get_correlation_id,
    get_logger,
    set_correlation_id,
)


@pytest.fixture(autouse=True)
def _reset_logging_state() -> Iterator[None]:
    """Ensure each logging test starts from a clean config."""
    _reset_for_tests()
    yield
    _reset_for_tests()
    set_correlation_id(None)


def test_logger_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO")
    log = get_logger("test")
    log.info("hello", k="v")
    out = capsys.readouterr().out
    line = out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "hello"
    assert payload["k"] == "v"
    assert payload["level"] == "info"
    assert payload["logger"] == "test"
    assert "timestamp" in payload


def test_correlation_id_injected_in_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="INFO")
    log = get_logger("test")
    set_correlation_id("cid-123")
    log.info("with-cid")
    out = capsys.readouterr().out
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["correlation_id"] == "cid-123"
    assert get_correlation_id() == "cid-123"


def test_configure_is_idempotent() -> None:
    configure_logging()
    configure_logging()
    configure_logging(level="DEBUG")
