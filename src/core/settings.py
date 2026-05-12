"""Settings — pydantic-settings v2.

All configuration flows through `Settings`. Reads from environment then `.env`
file (development only). Production runs without `.env`; the orchestrator
injects env vars from secrets.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Core ----
    env: Literal["dev", "staging", "prod", "test"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    app_version: str = "0.1.0"

    # ---- Database / cache ----
    database_url: str = Field(
        default="postgresql+asyncpg://ede:ede@postgres:5432/ede",
        description="SQLAlchemy async URL.",
    )
    redis_url: str = Field(default="redis://redis:6379/0")

    # ---- API ----
    api_host: str = "0.0.0.0"  # noqa: S104 — bound inside container only, port-mapped to 127.0.0.1
    api_port: int = 8000
    ede_api_token: SecretStr = SecretStr("changeme")

    # ---- IBKR (phase 5) ----
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 42
    ibkr_paper: bool = True

    # ---- Anthropic / Analyst (phase 8) ----
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-opus-4-7"
    analyst_daily_budget_usd: float = 2.0

    # ---- GDELT (phase 5) ----
    gcp_service_account_json: str = ""
    gcp_project_id: str = ""

    # ---- Discord (phase 11) ----
    discord_webhook_alerts: SecretStr = SecretStr("")
    discord_webhook_digest: SecretStr = SecretStr("")

    # ---- Obsidian (phase 8) ----
    obsidian_vault_path: str = "/mnt/obsidian/EDE"

    # ---- Scraping ----
    user_agent: str = "EDE-Bot/0.1 (research; contact@example.com)"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton. Tests can clear the cache."""
    return Settings()
