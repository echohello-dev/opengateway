"""Routing layer for the Mojo bridge (issue #4).

Two responsibilities, both pure helpers so the bridge stays symmetric
between the streaming and non-streaming paths:

1. ``resolve_route``: look up the ``RouteRule`` for a model. Returns
   ``None`` when the model has no explicit rule; the bridge then falls
   back to the legacy prefix-based provider selection.
2. ``estimate_request_cost_usd``: best-effort upper bound on what this
   request will cost upstream. Drives the per-key ``max_cost_usd`` cap.
3. ``chat_with_fallback``: try the primary provider, and on a retryable
   failure (5xx / 429 / connection error) try a configured fallback
   provider exactly once. Streaming variant falls back only before the
   first frame is queued (mid-stream fallback would violate the SSE
   client contract).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from opengateway.config import RouteRule, get_settings
from opengateway.providers.base import BaseProvider

logger = logging.getLogger("opengateway.mojo_bridge.routing")

_OpenAIEnvelope = dict[str, Any]


# Conservative average-chars-per-token for OpenAI-compatible tokenisers.
# Used for the prompt-cost estimate; over-estimation is the safe bias
# for a cap.
_CHARS_PER_TOKEN = 4


# Provider module name → settings field name. Keep this table small:
# adding a provider means adding both a key here and a row to the
# default ``_PREFIX_ROUTE`` fallback.
_PROVIDER_MODULE_TO_SETTINGS_API_KEY = {
    "opengateway.providers.openai": "openai_api_key",
    "opengateway.providers.anthropic": "anthropic_api_key",
}

_PROVIDER_MODULE_TO_SETTINGS_BASE_URL = {
    "opengateway.providers.openai": "openai_base_url",
    "opengateway.providers.anthropic": "anthropic_base_url",
}

# Legacy prefix-based fallback when ``settings.routes`` is empty.
# Mirrors ``opengateway/mojo/main.mojo::_select_provider_module`` and
# ``opengateway/mojo/test_router.mojo::select_provider_module``. Drift
# is guarded by ``tests/test_mojo_bridge.py::test_routing_rules_match_mojo_router``.
_PREFIX_TO_MODULE = {
    "gpt-": "opengateway.providers.openai",
    "openai/": "opengateway.providers.openai",
    "claude-": "opengateway.providers.anthropic",
    "anthropic/": "opengateway.providers.anthropic",
    "bedrock/": "opengateway.providers.bedrock",
    "amazon.": "opengateway.providers.bedrock",
}


def resolve_route(model: str, default_module: str = "") -> tuple[RouteRule | None, str]:
    """Return the ``RouteRule`` for ``model`` (or ``None``) and the
    provider module name to use.

    When ``settings.routes`` is non-empty and contains an entry for
    ``model``, that rule wins. Otherwise we fall through to the
    caller-supplied ``default_module`` (the Mojo router's prefix-based
    guess), and finally to the prefix table so pre-#4 deployments
    route identically to before.

    Returns a ``(rule, provider_module)`` tuple. ``rule`` is ``None``
    when falling through to the prefix table (no pricing available —
    the bridge skips the cost cap in that case).
    """
    settings = get_settings()
    for rule in settings.routes:
        if rule.model == model:
            return rule, _module_name_for(rule.primary)

    if default_module:
        return None, default_module
    return None, _prefix_to_module(model)


def _module_name_for(provider: str) -> str:
    """Translate a ``RouteRule.primary`` / ``fallback`` short name into a
    fully-qualified module path. ``openai`` → ``opengateway.providers.openai``,
    ``anthropic`` → ``opengateway.providers.anthropic``. Unknown names
    pass through as ``opengateway.providers.<name>`` so custom adapters
    registered under ``opengateway/providers/`` work without an explicit
    mapping here.
    """
    if "." in provider:
        return provider
    return f"opengateway.providers.{provider}"


def _prefix_to_module(model: str) -> str:
    for prefix, module in _PREFIX_TO_MODULE.items():
        if model.startswith(prefix):
            return module
    return ""


def resolve_provider_api_key(provider_module: str) -> str | None:
    """Return the configured API key for ``provider_module``, or ``None``."""
    settings = get_settings()
    field = _PROVIDER_MODULE_TO_SETTINGS_API_KEY.get(provider_module)
    if field is None:
        return None
    value = getattr(settings, field, None)
    return str(value) if value else None


def resolve_provider_base_url(provider_module: str) -> str | None:
    """Return the configured base URL override for ``provider_module``."""
    settings = get_settings()
    field = _PROVIDER_MODULE_TO_SETTINGS_BASE_URL.get(provider_module)
    if field is None:
        return None
    value = getattr(settings, field, None)
    return str(value) if value else None


def estimate_request_cost_usd(rule: RouteRule, body: dict[str, Any]) -> float:
    """Upper-bound estimate of the upstream dollar cost for ``body``.

    Inputs are estimated by JSON-serialising the messages and dividing
    by ``_CHARS_PER_TOKEN``; outputs are bounded by either the
    request's ``max_tokens`` (when present) or the rule's
    ``max_output_tokens`` (when set). Worst-case is the right bias for
    a cost cap.
    """
    try:
        prompt_chars = len(json.dumps(body.get("messages", []), default=str))
    except (TypeError, ValueError):
        prompt_chars = 0
    prompt_tokens = max(1, prompt_chars // _CHARS_PER_TOKEN)

    max_completion = body.get("max_tokens")
    if max_completion is None:
        max_completion = rule.max_output_tokens
    if max_completion is None:
        # Last-resort ceiling so a misconfigured rule can't make the
        # estimate silently zero. 4k is a common default for cheap
        # models and won't over-estimate by orders of magnitude.
        max_completion = 4096

    prompt_cost = (prompt_tokens / 1000.0) * rule.input_price_per_1k
    output_cost = (int(max_completion) / 1000.0) * rule.output_price_per_1k
    return prompt_cost + output_cost


def is_retryable_error(exc: BaseException) -> bool:
    """True for failures where a same-request retry against another
    provider is likely to succeed.

    Covers the canonical transient set: 5xx upstream, 429 too-many-
    requests, and transport-level connection / timeout errors. 4xx
    other than 429 (auth, validation, schema) are *not* retryable —
    the request is broken, not the provider.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status >= 500 or status == 429
    return isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.RemoteProtocolError,
            ConnectionError,
        ),
    )


# ── Fallback orchestration ────────────────────────────────────────────────


class _RetryableError(RuntimeError):
    """Internal signal: a provider call failed with a retryable error.

    Raised by the chat helpers in this module when ``chat_with_fallback``
    should swap to the configured fallback provider. Carries the original
    exception so the bridge can surface it when both providers fail.
    """

    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original = original


def _provider_call_kwargs(provider_module: str, body: dict[str, Any]) -> tuple[str, str | None]:
    """Resolve the API key + base URL for ``provider_module``.

    Only enforces "API key configured" for modules with a registered
    key field (``openai``, ``anthropic``). Custom adapters and test
    stubs that don't need a real key are passed through; their
    provider class can decide what to do with ``""``.
    """
    api_key = resolve_provider_api_key(provider_module)
    if not api_key and provider_module in _PROVIDER_MODULE_TO_SETTINGS_API_KEY:
        raise RuntimeError(f"no API key configured for provider {provider_module}")
    return api_key or "", resolve_provider_base_url(provider_module)


async def _provider_chat(provider_module: str, body: dict[str, Any]) -> _OpenAIEnvelope:
    """Run a single non-streaming provider call, mapping transient
    failures to ``_RetryableError`` so ``chat_with_fallback`` can pick them
    up, and mapping non-retryable upstream HTTP errors to a plain
    ``RuntimeError`` so the bridge surfaces them as 502 (the
    conventional OpenAI-shaped upstream-error code).
    """
    from opengateway.mojo_bridge.chat import (
        _load_provider_class,
        _to_chat_request,
        _to_openai_response,
    )

    api_key, base_url = _provider_call_kwargs(provider_module, body)
    provider_cls = _load_provider_class(provider_module)
    provider = provider_cls(api_key=api_key, base_url=base_url)
    try:
        request = _to_chat_request(body)
        response = await provider.chat(request)
    except Exception as exc:
        if is_retryable_error(exc):
            raise _RetryableError(exc) from exc
        if isinstance(exc, httpx.HTTPStatusError):
            # Non-retryable upstream HTTP error (4xx other than 429):
            # the bridge should return 502 upstream_error, not 500
            # internal_error, since this is the provider failing, not
            # us.
            raise RuntimeError(
                f"upstream provider {provider_module} returned {exc.response.status_code}"
            ) from exc
        raise
    finally:
        await provider.close()

    return _to_openai_response(response)


async def chat_with_fallback(
    body: dict[str, Any],
    *,
    primary_module: str,
    fallback_module: str | None,
) -> tuple[_OpenAIEnvelope, str]:
    """Run the primary provider, falling back to ``fallback_module`` once
    on a retryable failure.

    Returns ``(openai_envelope, used_module)``. ``used_module`` lets the
    caller log which path actually served the request.
    """
    try:
        result = await _provider_chat(primary_module, body)
        return result, primary_module
    except _RetryableError as primary_exc:
        if fallback_module is None or fallback_module == primary_module:
            exc = _provider_failure(primary_module, primary_exc.original)
            raise exc from primary_exc.original
        logger.info(
            "primary provider failed; retrying on fallback",
            extra={"primary": primary_module, "fallback": fallback_module},
            exc_info=primary_exc.original,
        )
        try:
            result = await _provider_chat(fallback_module, body)
            return result, fallback_module
        except _RetryableError as fallback_exc:
            exc = _provider_failure(fallback_module, fallback_exc.original)
            raise exc from primary_exc.original


def _provider_failure(provider_module: str, exc: BaseException) -> RuntimeError:
    """Build the ``RuntimeError`` the bridge maps to 502. Caller does the raise."""
    return RuntimeError(f"upstream provider {provider_module} failed: {exc!r}")


# ── Streaming variant (pre-first-frame fallback only) ─────────────────────


class StreamFallbackError(Exception):
    """Raised when primary streaming fails before any frame is queued and
    fallback is either unset or also fails before its first frame.

    Wraps the original exception so the bridge can surface 502.
    """

    def __init__(self, original: BaseException, *, on_fallback: bool) -> None:
        super().__init__(str(original))
        self.original = original
        self.on_fallback = on_fallback


async def chat_stream_with_fallback(
    body: dict[str, Any],
    *,
    primary_module: str,
    fallback_module: str | None,
    cancel: Any,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames from the primary provider, transparently
    retrying on the fallback *before the first frame is emitted*.

    Mid-stream errors (after frames have started) are not retried: the
    client already committed to receiving a stream from the primary
    provider, and silently swapping mid-flight would corrupt the SSE
    shape. The caller (``StreamHandle._run``) logs the failure and
    emits ``data: [DONE]`` so the client gets a clean terminator.
    """
    from opengateway.mojo_bridge.chat import (
        _to_chat_request,
    )

    # ── Primary attempt ─────────────────────────────────────────────────
    primary = _instantiate_provider(primary_module, body)
    primary_failed: BaseException | None = None
    try:
        request = _to_chat_request(body, stream=True)
        iterator = primary.chat_stream(request)
        first = await _anext_or_none(iterator)
        if first is None:
            return
        yield first
        if cancel.is_set():
            return
        async for chunk in iterator:
            if cancel.is_set():
                return
            yield chunk
        return
    except Exception as exc:
        if not is_retryable_error(exc):
            raise StreamFallbackError(exc, on_fallback=False) from exc
        primary_failed = exc
        logger.info(
            "streaming primary failed before first frame",
            extra={"primary": primary_module},
            exc_info=exc,
        )
    finally:
        await primary.close()

    # ── Fallback attempt ───────────────────────────────────────────────
    if fallback_module is None or fallback_module == primary_module or primary_failed is None:
        raise StreamFallbackError(
            primary_failed or RuntimeError("primary failed"), on_fallback=False
        )

    logger.info(
        "retried streaming on fallback",
        extra={"primary": primary_module, "fallback": fallback_module},
    )
    fallback = _instantiate_provider(fallback_module, body)
    try:
        request = _to_chat_request(body, stream=True)
        iterator = fallback.chat_stream(request)
        first = await _anext_or_none(iterator)
        if first is None:
            return
        yield first
        if cancel.is_set():
            return
        async for chunk in iterator:
            if cancel.is_set():
                return
            yield chunk
    except Exception as exc:
        raise StreamFallbackError(exc, on_fallback=True) from primary_failed
    finally:
        await fallback.close()


def _instantiate_provider(provider_module: str, body: dict[str, Any]) -> BaseProvider:
    from opengateway.mojo_bridge.chat import _load_provider_class

    api_key, base_url = _provider_call_kwargs(provider_module, body)
    provider_cls = _load_provider_class(provider_module)
    instance: BaseProvider = provider_cls(api_key=api_key, base_url=base_url)
    return instance


async def _anext_or_none(iterator: AsyncGenerator[str, None]) -> str | None:
    """Pull the first item from ``iterator``; return ``None`` if it's
    exhausted without yielding.
    """
    try:
        return await iterator.__anext__()
    except StopAsyncIteration:
        return None
