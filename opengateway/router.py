from __future__ import annotations

import os
from typing import Any

from opengateway.providers.base import BaseProvider
from opengateway.providers.openai import OpenAIProvider


class Router:
    """Simple model router that selects the appropriate provider."""

    def __init__(self, registry: dict[str, Any] | None = None) -> None:
        self._registry = registry or {}
        self._providers: dict[str, BaseProvider] = {}

    def select_provider(self, model: str) -> BaseProvider | None:
        """Select a provider for the given model."""
        # For now, simple OpenAI routing
        if model.startswith("gpt-") or model.startswith("openai/"):
            provider_key = "openai"
        else:
            provider_key = "openai"  # Default fallback for minimal version

        if provider_key not in self._providers:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return None
            self._providers[provider_key] = OpenAIProvider(api_key=api_key)

        return self._providers[provider_key]

    def reset(self) -> None:
        """Close all provider connections."""
        for provider in self._providers.values():
            pass  # Providers handle their own lifecycle
        self._providers.clear()
