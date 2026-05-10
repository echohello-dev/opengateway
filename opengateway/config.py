from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Database
    database_url: PostgresDsn = Field(
        default="postgresql://postgres:postgres@localhost:5432/opengateway"
    )
    database_pool_size: int = Field(default=10)

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")

    # Providers
    default_timeout: int = Field(default=60)
    max_retries: int = Field(default=2)
    retry_backoff: float = Field(default=1.0)

    # Observability
    enable_metrics: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    @property
    def database_url_str(self) -> str:
        return str(self.database_url)

    @property
    def redis_url_str(self) -> str:
        return str(self.redis_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
