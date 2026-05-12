"""Tests for src.core.settings."""

from __future__ import annotations

import pytest

from src.core.settings import Settings, get_settings


def test_settings_defaults_in_test_env() -> None:
    settings = get_settings()
    assert settings.env == "test"
    assert settings.app_version == "0.1.0"
    assert settings.is_prod is False


def test_settings_token_is_secret() -> None:
    settings = get_settings()
    # SecretStr never leaks via repr
    assert "test-token" not in repr(settings)
    assert settings.ede_api_token.get_secret_value() == "test-token"


def test_settings_invalid_env_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "banana")
    get_settings.cache_clear()
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        Settings()
