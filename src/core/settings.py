"""Settings — pydantic-settings v2.

All configuration flows through `Settings`. Reads from environment then `.env`
file (development only). Production runs without `.env`; the orchestrator
injects env vars from secrets.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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

    # ---- Trading (phase 8 — paper) ----
    trading_min_spread_pct: float = 0.01  # skip deals with < 1% edge vs offer
    trading_entry_offset_quoted: float = 0.001  # FR/DE limit = mid * (1 + 0.1%)
    trading_entry_offset_last: float = 0.004  # IT limit = last * (1 + 0.4%) (no bid/ask)
    trading_stop_loss_pct: float = 0.10  # stop = entry * (1 - 10%)
    trading_min_score_stars: int = 3
    trading_rampup_required: int = 5  # first N trades need manual approval
    trading_daily_loss_limit_pct: float = 0.02  # auto-shutdown at -2% day
    trading_order_cooldown_min: int = 60  # min minutes between orders
    trading_heartbeat_hours: int = 4
    trading_timezone: str = "Europe/Paris"  # DST-aware cron (decision #4)
    # V1 scope: DE only (BaFin publishes ISIN ⇒ reliable ticker resolution).
    # CSV env, e.g. TRADING_ALLOWED_JURISDICTIONS=DE,FR,IT (after Phase-9 ISIN extraction).
    trading_allowed_jurisdictions: list[str] = Field(default_factory=lambda: ["DE"])

    @field_validator("trading_allowed_jurisdictions", mode="before")
    @classmethod
    def _parse_csv_jurisdictions(cls, v: object) -> object:
        if isinstance(v, str):
            return [x.strip().upper() for x in v.split(",") if x.strip()]
        return v

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
    user_agent: str = "EDE-Bot/0.1 (research; contact via repo)"

    # ---- Storage paths ----
    # PDFs land under ${data_dir}/pdfs/{juridiction}/{year}/{regulator_ref}.pdf.
    # Default ./data on local Windows dev; override to /app/data inside Docker
    # (set by docker-compose) or /data on the Oracle VM.
    data_dir: str = "./data"

    # ---- AMF poller (phase 2) ----
    amf_rss_url: str = "https://www.amf-france.org/fr/flux-rss/display/23"
    poller_amf_interval_minutes: int = 15
    poller_amf_rate_per_second: float = 1.0
    poller_amf_jitter_seconds: float = 0.2
    poller_amf_max_retries: int = 3
    poller_amf_timeout_seconds: float = 30.0
    poller_amf_accept_language: str = "fr-FR,fr;q=0.9"

    # ---- ScrapingBee (phase 4: Consob — Radware bypass) ----
    # Free Tier = 1000 credits/month. Hard budget enforced at 900 to leave
    # headroom for the next month's first incremental polls.
    #
    # Empirically (2026-05-19): Consob's documenti-opa listing returns
    # the full HTML (152 KB, 50 rows) even with render_js=false and
    # premium_proxy=false → 1 credit/call. PDFs at /documents/ are NOT
    # Radware-protected and download via plain httpx (0 credits).
    scrapingbee_api_key: SecretStr = SecretStr("")
    scrapingbee_base_url: str = "https://app.scrapingbee.com/api/v1/"
    scrapingbee_monthly_budget: int = 900
    # Comma-separated % thresholds at which a Discord alert fires (phase 11).
    scrapingbee_alert_thresholds: str = "50,75,90"
    scrapingbee_timeout_seconds: float = 60.0
    # Cost-optimisation defaults — escalate only if Radware tightens.
    scrapingbee_render_js: bool = False
    scrapingbee_premium_proxy: bool = False
    scrapingbee_country_code: str = "it"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def scrapingbee_alert_threshold_pcts(self) -> tuple[int, ...]:
        parts = (x.strip() for x in self.scrapingbee_alert_thresholds.split(","))
        return tuple(sorted(int(p) for p in parts if p))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton. Tests can clear the cache."""
    return Settings()
