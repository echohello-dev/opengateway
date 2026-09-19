from __future__ import annotations

import os

from opengateway.providers.base import BaseProvider
from opengateway.providers.openai import OpenAIProvider


class Router:
    """Resolve a model string to a ``BaseProvider`` for the FastAPI dev path.

    Prefers the explicit ``routes`` table from ``Settings`` when
    populated (issue #4); falls back to the prefix-based defaults so
    deployments without a configured routing table behave identically
    to before.
    """

    def __init__(self, registry: dict[str, BaseProvider] | None = None) -> None:
        self._providers: dict[str, BaseProvider] = registry or {}

    def select_provider(self, model: str) -> BaseProvider | None:
        provider_key = self._select_provider_key(model)
        if provider_key == "":
            return None

        if provider_key not in self._providers:
            api_key = self._api_key_for(provider_key)
            if not api_key:
                return None
            base_url = self._base_url_for(provider_key)
            self._providers[provider_key] = OpenAIProvider(api_key=api_key, base_url=base_url)
        return self._providers[provider_key]

    def _select_provider_key(self, model: str) -> str:
        try:
            from opengateway.config import get_settings

            settings = get_settings()
            for rule in settings.routes:
                if rule.model == model:
                    return f"opengateway.providers.{rule.primary}"
        except Exception:
            pass

        if model.startswith("gpt-") or model.startswith("openai/"):
            return "opengateway.providers.openai"
        return "opengateway.providers.openai"

    @staticmethod
    def _api_key_for(provider_key: str) -> str:
        if provider_key == "opengateway.providers.openai":
            return os.environ.get("OPENAI_API_KEY", "")
        if provider_key == "opengateway.providers.anthropic":
            return os.environ.get("ANTHROPIC_API_KEY", "")
        return ""

    @staticmethod
    def _base_url_for(provider_key: str) -> str | None:
        if provider_key == "opengateway.providers.openai":
            return os.environ.get("OPENAI_BASE_URL") or None
        if provider_key == "opengateway.providers.anthropic":
            return os.environ.get("ANTHROPIC_BASE_URL") or None
        return None

    def reset(self) -> None:
        """Close all provider connections."""
        for _provider in self._providers.values():
            pass  # Providers handle their own lifecycle
        self._providers.clear()
