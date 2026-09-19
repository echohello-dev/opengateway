from __future__ import annotations

import json
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RouteRule(BaseSettings):
    """One per-model routing rule.

    Each rule pins a primary provider and (optionally) a fallback
    provider that the bridge retries on retryable failures. Pricing
    fields drive the per-virtual-key dollar cost cap (``max_cost_usd``).

    Sourced from the ``ROUTES_JSON`` environment variable as a JSON
    array. Empty list ⇒ prefix-based fallback (``gpt-*`` → OpenAI,
    ``claude-*`` → Anthropic, etc.) is used, preserving pre-#4
    behaviour.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str
    primary: str
    fallback: str | None = None
    input_price_per_1k: float = 0.0
    output_price_per_1k: float = 0.0
    max_output_tokens: int | None = None


class Settings(BaseSettings):
    """Gateway configuration. All values can be overridden via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = Field(default="opengateway")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    workers: int = Field(default=1)

    # Auth
    root_key: str = Field(default="sk-root-change-me")
    require_auth: bool = Field(default=True)

    # Database (unset = root-key-only auth, no persistence)
    database_url: str | None = Field(default=None)
    database_pool_size: int = Field(default=10)

    # Redis (unset = no distributed rate limiting)
    redis_url: str | None = Field(default=None)

    # Providers
    openai_api_key: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    openai_base_url: str | None = Field(default=None)
    anthropic_base_url: str | None = Field(default=None)
    default_timeout: int = Field(default=60)
    max_retries: int = Field(default=2)
    retry_backoff: float = Field(default=1.0)

    # Routes (empty list = prefix-based fallback; see RouteRule docstring).
    # Aliases ``ROUTES_JSON`` for the env var name, falls back to the
    # field name ``routes`` so tests can also construct ``Settings``
    # directly with ``routes=[...]``.
    routes: list[RouteRule] = Field(
        default_factory=list,
        validation_alias=AliasChoices("ROUTES_JSON", "routes"),
    )

    # Observability
    enable_metrics: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    @field_validator("routes", mode="before")
    @classmethod
    def _parse_routes(cls, value: object) -> object:
        """Accept ``ROUTES_JSON`` as a JSON string or an already-parsed list."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"ROUTES_JSON is not valid JSON: {exc}") from exc
            if not isinstance(parsed, list):
                raise ValueError("ROUTES_JSON must be a JSON array of route objects")
            return parsed
        return value

    @property
    def database_url_str(self) -> str | None:
        return str(self.database_url) if self.database_url else None

    @property
    def redis_url_str(self) -> str | None:
        return str(self.redis_url) if self.redis_url else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
