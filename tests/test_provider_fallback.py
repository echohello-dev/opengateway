"""Tests for single-hop provider fallback routing (issue #4).

Fallback retries only on retryable failures (5xx, 429, connection /
timeout errors). 4xx other than 429 (auth, validation, schema) do not
trigger a fallback. Streaming falls back only before the first frame
is queued — mid-stream errors are surfaced, not silently swapped.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any

import httpx
import pytest

from opengateway.mojo_bridge import handle_chat
from opengateway.mojo_bridge.auth import _hash_key
from opengateway.mojo_bridge.routing import (
    StreamFallbackError,
    chat_stream_with_fallback,
    chat_with_fallback,
    is_retryable_error,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Any:
    from opengateway.config import get_settings
    from opengateway.mojo_bridge import auth as bridge_auth
    from opengateway.mojo_bridge.db import reset_store_cache
    from opengateway.mojo_bridge.ratelimit import reset_limiter_cache

    get_settings.cache_clear()
    bridge_auth._cache.clear()
    reset_store_cache()
    reset_limiter_cache()
    yield
    get_settings.cache_clear()
    bridge_auth._cache.clear()
    reset_store_cache()
    reset_limiter_cache()


ROUTES = [
    {
        "model": "gpt-4o",
        "primary": "openai",
        "fallback": "anthropic",
        "input_price_per_1k": 0.0025,
        "output_price_per_1k": 0.01,
    },
    {
        "model": "no-fallback-model",
        "primary": "openai",
        "input_price_per_1k": 0.0025,
        "output_price_per_1k": 0.01,
    },
]


def _set_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTES_JSON", json.dumps(ROUTES))


class _FakeStore:
    def __init__(self, records: dict[str, Any]) -> None:
        self._records = records

    def lookup(self, key_hash: str) -> Any:
        return self._records.get(key_hash)

    def record_usage(self, key_id: str, total_tokens: int) -> None:  # pragma: no cover
        pass


def _fake_record(**overrides: Any) -> Any:
    from opengateway.mojo_bridge.db import VirtualKeyRecord

    defaults: dict[str, Any] = {
        "key_id": "vk_test",
        "name": "test-key",
        "is_admin": False,
        "models": None,
        "max_budget": None,
        "budget_used": 0.0,
        "max_cost_usd": None,
        "tpm_limit": None,
        "rpm_limit": None,
    }
    defaults.update(overrides)
    return VirtualKeyRecord(**defaults)


def _register_provider(
    module_name: str,
    *,
    chat_behaviour: Any,
    chunks: list[str] | None = None,
) -> None:
    """Install a stub provider module so the bridge resolves a class.

    ``chat_behaviour`` is one of:
      - a ``BaseException`` instance/cls to raise from ``chat()``
      - a ``ChatResponse`` to return from ``chat()``
      - a callable ``(request) -> ChatResponse``

    The fake lives at ``module_name``. The caller is responsible for
    setting an env var (e.g. ``OPENAI_API_KEY``) so the bridge's API
    key lookup for the *real* provider at the same long name doesn't
    fail. For tests that don't go through the routing layer (i.e. call
    ``_provider_chat`` directly with the fake's module name), the key
    isn't checked.
    """
    from opengateway.providers.base import BaseProvider, ChatResponse

    class FakeProvider(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            if isinstance(chat_behaviour, BaseException):
                raise chat_behaviour
            if callable(chat_behaviour):
                return chat_behaviour(request)
            return chat_behaviour

        async def chat_stream(self, request: Any):
            if chunks is None:
                return
            for text in chunks:
                yield text

        async def close(self) -> None:
            return None

    module = types.ModuleType(module_name)
    class_name = module_name.rsplit(".", 1)[-1].capitalize() + "Provider"
    setattr(module, class_name, FakeProvider)
    sys.modules[module_name] = module


# ── is_retryable_error ─────────────────────────────────────────────────────


def test_is_retryable_error_classifies_5xx() -> None:
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    response = httpx.Response(503, request=request)
    exc = httpx.HTTPStatusError("boom", request=request, response=response)
    assert is_retryable_error(exc) is True


def test_is_retryable_error_classifies_429() -> None:
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(429, request=request)
    exc = httpx.HTTPStatusError("rate", request=request, response=response)
    assert is_retryable_error(exc) is True


def test_is_retryable_error_rejects_4xx_other_than_429() -> None:
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(401, request=request)
    exc = httpx.HTTPStatusError("auth", request=request, response=response)
    assert is_retryable_error(exc) is False


def test_is_retryable_error_classifies_connection_errors() -> None:
    assert is_retryable_error(httpx.ConnectError("nope"))
    assert is_retryable_error(httpx.ReadTimeout("slow"))


# ── chat_with_fallback (non-streaming) ─────────────────────────────────────


def test_chat_falls_back_on_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Primary 5xx → fallback succeeds, response shape preserved."""
    from opengateway.providers.base import ChatResponse

    _set_routes(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(503, request=request)
    primary_exc = httpx.HTTPStatusError("server", request=request, response=response)

    import opengateway.providers.anthropic as anthropic_mod
    import opengateway.providers.openai as openai_mod
    from opengateway.providers.base import BaseProvider

    class _Boom(BaseProvider):
        async def chat(self, request: Any) -> Any:
            raise primary_exc

        async def chat_stream(self, request: Any):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    class _Ok(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            return ChatResponse(
                id="chatcmpl-fb",
                model=request.model,
                content="fallback-ok",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                finish_reason="stop",
            )

        async def chat_stream(self, request: Any):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    monkeypatch.setattr(openai_mod, "OpenAIProvider", _Boom)
    monkeypatch.setattr(anthropic_mod, "AnthropicProvider", _Ok)

    import asyncio

    result, used = asyncio.run(
        chat_with_fallback(
            body={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            primary_module="opengateway.providers.openai",
            fallback_module="opengateway.providers.anthropic",
        )
    )
    assert used == "opengateway.providers.anthropic"
    assert "fallback-ok" in json.dumps(result)


def test_chat_does_not_fall_back_on_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-retryable failure (400) does NOT trigger fallback."""
    from opengateway.providers.base import BaseProvider, ChatResponse

    _set_routes(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(400, request=request)
    primary_exc = httpx.HTTPStatusError("bad request", request=request, response=response)

    fallback_called = {"count": 0}

    class _Boom(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            raise primary_exc

        async def chat_stream(self, request: Any):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    class _Ok(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            fallback_called["count"] += 1
            return ChatResponse(
                id="x", model=request.model, content="x", usage={}, finish_reason="stop"
            )

        async def chat_stream(self, request: Any):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    import opengateway.providers.anthropic as anthropic_mod
    import opengateway.providers.openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAIProvider", _Boom)
    monkeypatch.setattr(anthropic_mod, "AnthropicProvider", _Ok)

    import asyncio

    # Bridge contract: non-retryable upstream failure surfaces as a
    # RuntimeError so the mapper emits a 502 upstream_error envelope.
    # The original exception is preserved in the chain.
    with pytest.raises(RuntimeError, match="upstream provider .* returned 400"):
        asyncio.run(
            chat_with_fallback(
                body={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
                primary_module="opengateway.providers.openai",
                fallback_module="opengateway.providers.anthropic",
            )
        )
    assert fallback_called["count"] == 0


def test_chat_no_fallback_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """No fallback in the route → primary failure surfaces directly."""
    request = httpx.Request("POST", "https://api.openai.com")
    response = httpx.Response(500, request=request)
    primary_exc = httpx.HTTPStatusError("boom", request=request, response=response)

    _set_routes(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    # Swap OpenAIProvider for a fake that raises our prebuilt exc.
    import opengateway.providers.openai as openai_mod
    from opengateway.providers.base import BaseProvider, ChatResponse

    class _Boom(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            raise primary_exc

        async def chat_stream(self, request: Any):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    monkeypatch.setattr(openai_mod, "OpenAIProvider", _Boom)

    import asyncio

    with pytest.raises(RuntimeError, match="upstream provider .* failed"):
        asyncio.run(
            chat_with_fallback(
                body={
                    "model": "no-fallback-model",
                    "messages": [{"role": "user", "content": "hi"}],
                },
                primary_module="opengateway.providers.openai",
                fallback_module=None,
            )
        )


# ── End-to-end via handle_chat ────────────────────────────────────────────


def test_handle_chat_uses_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_routes(monkeypatch)
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record()})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(502, request=request)
    primary_exc = httpx.HTTPStatusError("bad gateway", request=request, response=response)

    # Primary 502 on openai (retryable → falls back), anthropic returns ok.
    import opengateway.providers.anthropic as anthropic_mod  # noqa: F401
    import opengateway.providers.openai as openai_mod
    from opengateway.providers.base import BaseProvider, ChatResponse

    class _Boom(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            raise primary_exc

        async def chat_stream(self, request: Any):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    class _Ok(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            return ChatResponse(
                id="x",
                model=request.model,
                content="via-anthropic",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                finish_reason="stop",
            )

        async def chat_stream(self, request: Any):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    monkeypatch.setattr(openai_mod, "OpenAIProvider", _Boom)

    # The route's fallback is "anthropic", so the module path resolves
    # to ``opengateway.providers.anthropic``. We swap AnthropicProvider
    # for our _Ok fake so it returns success.
    monkeypatch.setattr(anthropic_mod, "AnthropicProvider", _Ok)

    envelope = handle_chat(
        body={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 200
    assert "via-anthropic" in envelope["body"]


def test_handle_chat_returns_502_when_both_providers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bridge maps both-providers-failed to a 502 envelope."""
    _set_routes(monkeypatch)
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record()})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    request = httpx.Request("POST", "https://api.example.com")
    response = httpx.Response(500, request=request)
    both_exc = httpx.HTTPStatusError("boom", request=request, response=response)

    import opengateway.providers.anthropic as anthropic_mod
    import opengateway.providers.openai as openai_mod
    from opengateway.providers.base import BaseProvider, ChatResponse

    class _Boom(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            raise both_exc

        async def chat_stream(self, request: Any):
            if False:
                yield ""

        async def close(self) -> None:
            return None

    monkeypatch.setattr(openai_mod, "OpenAIProvider", _Boom)
    monkeypatch.setattr(anthropic_mod, "AnthropicProvider", _Boom)

    envelope = handle_chat(
        body={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 502
    assert "upstream_error" in envelope["body"]


# ── Streaming fallback ─────────────────────────────────────────────────────


def _drain_stream(handle: Any) -> list[str]:
    frames: list[str] = []
    for _ in range(100):
        code, payload = handle.next_chunk(1.0)
        if code == 2:
            return frames
        if payload:
            frames.append(payload)
    raise AssertionError("stream never reached EOF")


def test_stream_falls_back_before_first_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Primary stream that errors before its first chunk triggers fallback."""
    import asyncio

    _set_routes(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(503, request=request)
    primary_exc = httpx.HTTPStatusError("down", request=request, response=response)

    import opengateway.providers.anthropic as anthropic_mod
    import opengateway.providers.openai as openai_mod
    from opengateway.providers.base import BaseProvider, ChatResponse

    class _Boom(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:  # pragma: no cover
            raise NotImplementedError

        async def chat_stream(self, request: Any):
            raise primary_exc
            yield ""  # pragma: no cover

        async def close(self) -> None:
            return None

    class _Ok(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:  # pragma: no cover
            raise NotImplementedError

        async def chat_stream(self, request: Any):
            yield "frame-from-anthropic"

        async def close(self) -> None:
            return None

    monkeypatch.setattr(openai_mod, "OpenAIProvider", _Boom)
    monkeypatch.setattr(anthropic_mod, "AnthropicProvider", _Ok)

    import threading

    cancel = threading.Event()
    frames = []

    async def collect() -> None:
        async for frame in chat_stream_with_fallback(
            body={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            primary_module="opengateway.providers.openai",
            fallback_module="opengateway.providers.anthropic",
            cancel=cancel,
        ):
            frames.append(frame)

    asyncio.run(collect())
    assert frames == ["frame-from-anthropic"]


def test_stream_does_not_swallow_non_retryable_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mid-stream or pre-stream non-retryable errors surface as StreamFallbackError."""
    import asyncio

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")

    import opengateway.providers.openai as openai_mod
    from opengateway.providers.base import BaseProvider, ChatResponse

    class _Bad(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:  # pragma: no cover
            raise NotImplementedError

        async def chat_stream(self, request: Any):
            raise ValueError("bad payload")
            yield ""  # pragma: no cover

        async def close(self) -> None:
            return None

    monkeypatch.setattr(openai_mod, "OpenAIProvider", _Bad)

    import threading

    cancel = threading.Event()

    async def collect() -> None:
        async for _ in chat_stream_with_fallback(
            body={"model": "x", "messages": [{"role": "user", "content": "hi"}]},
            primary_module="opengateway.providers.openai",
            fallback_module=None,
            cancel=cancel,
        ):
            pass

    with pytest.raises(StreamFallbackError) as ei:
        asyncio.run(collect())
    assert ei.value.on_fallback is False
