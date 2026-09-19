"""Chat completion entry point callable from Mojo.

Synchronous wrapper around the async provider layer. Returns a JSON-serialisable
dict that the Mojo handler passes back through the bridge envelope.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from opengateway.mojo_bridge.auth import AuthResult, authenticate_authorization
from opengateway.mojo_bridge.db import record_usage_for
from opengateway.mojo_bridge.routing import (
    chat_with_fallback,
    estimate_request_cost_usd,
    resolve_route,
)
from opengateway.providers.base import ChatRequest

logger = logging.getLogger("opengateway.mojo_bridge.chat")


def health_check() -> dict[str, str]:
    return {"status": "ok"}


def chat_completion(
    body: dict[str, Any],
    authorization: str | None,
    provider_module: str,
) -> dict[str, Any]:
    """Drive a chat completion request synchronously.

    Args:
        body: OpenAI-compatible request body (model, messages, temperature, ...).
        authorization: Raw Authorization header value (may be None).
        provider_module: Fully-qualified Python module path that exposes a
            ``BaseProvider`` subclass for the requested model.

    Returns:
        OpenAI-compatible response dict.

    Raises:
        PermissionError: missing/invalid auth, model not allowed, budget exceeded.
        ValueError: unknown model or invalid request shape.
        RuntimeError: upstream provider failure.
    """
    auth = authenticate_authorization(authorization)
    _validate_request(body)
    route, resolved_primary = resolve_route(body["model"], default_module=provider_module)
    _enforce_model_access(auth, body["model"])
    _enforce_budget(auth)
    _enforce_cost_cap(auth, route, body)
    _enforce_rate_limit(auth)

    fallback_module = (
        _module_name_for(route.fallback) if route is not None and route.fallback else None
    )
    result, used_module = _run_with_fallback(
        body,
        primary_module=resolved_primary,
        fallback_module=fallback_module,
    )
    if used_module != resolved_primary and route is not None:
        logger.info(
            "chat served by fallback provider",
            extra={"model": body["model"], "fallback": used_module},
        )
    usage = result.get("usage") or {}
    record_usage_for(auth.key_id, int(usage.get("total_tokens", 0)))
    return result


def _run_with_fallback(
    body: dict[str, Any],
    *,
    primary_module: str,
    fallback_module: str | None,
) -> tuple[dict[str, Any], str]:
    """Drive the async fallback helper from a sync entry point.

    ``chat_with_fallback`` is async to give the streaming path a single
    shared abstraction; this thin wrapper is the sync-side adapter.
    """
    import asyncio

    return asyncio.run(
        chat_with_fallback(body, primary_module=primary_module, fallback_module=fallback_module)
    )


def _module_name_for(provider: str) -> str:
    if "." in provider:
        return provider
    return f"opengateway.providers.{provider}"


def _validate_request(body: dict[str, Any]) -> None:
    model = body.get("model")
    if not isinstance(model, str) or not model:
        raise ValueError("missing or empty field: model")
    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) == 0:
        raise ValueError("missing or empty field: messages")


def _enforce_model_access(auth: AuthResult, model: str) -> None:
    if auth.models is not None and model not in auth.models:
        raise PermissionError(f"model not allowed for this key: {model}")


def _enforce_budget(auth: AuthResult) -> None:
    """Token-denominated budget check (ADR-003 §166)."""
    if auth.max_budget is not None and auth.budget_used >= auth.max_budget:
        raise PermissionError("budget exceeded")


def _enforce_cost_cap(auth: AuthResult, route: Any, body: dict[str, Any]) -> None:
    """Per-key dollar cost cap (issue #4).

    Skipped when no route is configured (legacy prefix-based routing
    has no pricing data) or when the key has no cap. Over-estimation
    is the right bias here — better to reject than to overspend.

    The raised message contains the word ``budget`` so the bridge's
    exception mapper routes it to HTTP 429 / ``rate_limit_error``,
    matching the token-budget rejection shape.
    """
    if auth.max_cost_usd is None or route is None:
        return
    estimated = estimate_request_cost_usd(route, body)
    if estimated > auth.max_cost_usd:
        raise PermissionError(
            f"cost budget exceeded: estimated ${estimated:.4f} > "
            f"max_cost_usd ${auth.max_cost_usd:.4f}"
        )


def _enforce_rate_limit(auth: AuthResult) -> None:
    """Per-key RPM check against the distributed limiter.

    No-op when the key has no ``rpm_limit`` or no limiter is
    configured. Fails open on Redis errors (see ratelimit.py).
    """
    if auth.rpm_limit is None:
        return
    from opengateway.mojo_bridge.ratelimit import get_limiter

    limiter = get_limiter()
    if limiter is None:
        return
    if not limiter.allow(auth.key_id, auth.rpm_limit):
        raise PermissionError(f"rate limit exceeded: {auth.rpm_limit} rpm")


def _to_chat_request(body: dict[str, Any], *, stream: bool = False) -> ChatRequest:
    extra = {
        k: v
        for k, v in body.items()
        if k not in {"model", "messages", "temperature", "max_tokens", "top_p", "stream"}
    }
    if stream:
        # Guarantee a usage-bearing final chunk so the bridge can record
        # spend for streamed requests; spec-compliant for OpenAI-shaped
        # upstreams and harmless to clients.
        extra.setdefault("stream_options", {"include_usage": True})
    return ChatRequest(
        model=body["model"],
        messages=body["messages"],
        temperature=body.get("temperature"),
        max_tokens=body.get("max_tokens"),
        top_p=body.get("top_p"),
        stream=stream,
        extra=extra,
    )


def _to_openai_response(response: Any) -> dict[str, Any]:
    return {
        "id": response.id,
        "object": "chat.completion",
        "created": 0,
        "model": response.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response.content},
                "finish_reason": response.finish_reason,
            }
        ],
        "usage": response.usage,
    }


def _resolve_provider_api_key(provider_module: str) -> str | None:
    """Return the configured API key for ``provider_module``.

    Centralised in ``routing`` so the streaming path uses the same
    lookup. Kept here as a thin alias for the helpers below.
    """
    from opengateway.mojo_bridge.routing import resolve_provider_api_key

    return resolve_provider_api_key(provider_module)


def _resolve_provider_base_url(provider_module: str) -> str | None:
    from opengateway.mojo_bridge.routing import resolve_provider_base_url

    return resolve_provider_base_url(provider_module)


def _load_provider_class(provider_module: str) -> Any:
    """Load the provider class from ``provider_module``.

    Scans the module for the first concrete ``BaseProvider`` subclass
    rather than deriving a class name from the module name, so provider
    modules are free to name their class ``OpenAIProvider`` (not
    ``OpenaiProvider``) or anything else.
    """
    from opengateway.providers.base import BaseProvider

    module = importlib.import_module(provider_module)
    for attr in vars(module).values():
        if isinstance(attr, type) and issubclass(attr, BaseProvider) and attr is not BaseProvider:
            return attr
    raise RuntimeError(f"provider module {provider_module} has no provider class")
