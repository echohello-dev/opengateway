from __future__ import annotations

from opengateway.providers.base import BaseProvider


class ProviderNotConfiguredError(Exception):
    """A route matched the model, but the provider has no API key configured."""

    def __init__(self, provider_module: str) -> None:
        self.provider_module = provider_module
        super().__init__(f"no API key configured for provider {provider_module}")


class Router:
    """Resolve a model string to a ``BaseProvider`` for the FastAPI dev path.

    Delegates to the shared bridge resolvers
    (``opengateway.mojo_bridge.routing``) so both servers resolve
    models, API keys, and base URLs identically: the ``ROUTES_JSON``
    table when populated, the prefix fallback (``gpt-*`` → OpenAI,
    ``claude-*`` → Anthropic, ...) otherwise. Provider config is read
    from ``Settings`` (which loads ``.env`` and the process
    environment), not from ``os.environ`` directly.
    """

    def __init__(self, registry: dict[str, BaseProvider] | None = None) -> None:
        self._providers: dict[str, BaseProvider] = registry or {}

    def select_provider(self, model: str) -> BaseProvider | None:
        """Return the provider for ``model``, or ``None`` when no route matches.

        Raises :class:`ProviderNotConfiguredError` when a route matches
        but the provider has no API key configured, so callers can
        distinguish "unknown model" from "gateway not configured".
        """
        from opengateway.mojo_bridge.chat import _load_provider_class
        from opengateway.mojo_bridge.routing import _provider_call_kwargs, resolve_route

        _rule, provider_key = resolve_route(model)
        if not provider_key:
            return None

        if provider_key not in self._providers:
            try:
                api_key, base_url = _provider_call_kwargs(provider_key, {})
            except RuntimeError as exc:
                raise ProviderNotConfiguredError(provider_key) from exc
            provider_cls = _load_provider_class(provider_key)
            self._providers[provider_key] = provider_cls(api_key=api_key, base_url=base_url)
        return self._providers[provider_key]

    def reset(self) -> None:
        """Close all provider connections."""
        for _provider in self._providers.values():
            pass  # Providers handle their own lifecycle
        self._providers.clear()
