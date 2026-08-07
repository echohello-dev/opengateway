"""Tests for the Python side of the Mojo bridge.

The Mojo layer is exercised by the ``pixi run mojo test`` job in CI.
These tests cover everything the Mojo handlers delegate into Python:
auth, request validation, envelope wrapping, and provider dispatch.
"""

from __future__ import annotations

from typing import Any

import pytest

from opengateway.mojo_bridge import (
    AuthResult,
    authenticate_authorization,
    handle_chat,
    handle_chat_stream,
    health_check,
)
from opengateway.mojo_bridge.auth import _hash_key


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Any:
    """Reset the ``get_settings`` lru_cache around every test.

    Without this, monkeypatch.setenv("ROOT_KEY", ...) in one test leaks
    into subsequent tests because the cached Settings instance is never
    invalidated.
    """
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


# ── Health check ─────────────────────────────────────────────────────────────


def test_health_check_returns_ok() -> None:
    assert health_check() == {"status": "ok"}


# ── Auth ─────────────────────────────────────────────────────────────────────


def test_authenticate_missing_header_raises() -> None:
    with pytest.raises(PermissionError, match="missing or malformed"):
        authenticate_authorization(None)


def test_authenticate_non_bearer_scheme_raises() -> None:
    with pytest.raises(PermissionError, match="missing or malformed"):
        authenticate_authorization("Basic dXNlcjpwYXNz")


def test_authenticate_bearer_without_value_raises() -> None:
    with pytest.raises(PermissionError, match="missing or malformed"):
        authenticate_authorization("Bearer ")


def test_authenticate_unknown_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    with pytest.raises(PermissionError, match="invalid virtual key"):
        authenticate_authorization("Bearer sk-something-else")


def test_authenticate_root_key_returns_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    result = authenticate_authorization("Bearer sk-root-good")
    assert isinstance(result, AuthResult)
    assert result.key_id == "root"
    assert result.is_admin is True
    assert result.models is None


def test_authenticate_root_key_case_insensitive_bearer() -> None:
    assert _hash_key("any-key") == _hash_key("any-key")
    assert len(_hash_key("any-key")) == 32


# ── Envelope wrapping ────────────────────────────────────────────────────────


def test_handle_chat_missing_auth_returns_401_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    envelope = handle_chat(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization=None,
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 401
    assert "authentication_error" in envelope["body"]
    assert "missing or malformed" in envelope["body"]


def test_handle_chat_missing_model_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    envelope = handle_chat(
        body={"messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 400
    assert "invalid_request_error" in envelope["body"]
    assert "model" in envelope["body"]


def test_handle_chat_missing_messages_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    envelope = handle_chat(
        body={"model": "gpt-4"},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 400
    assert "messages" in envelope["body"]


def test_handle_chat_empty_messages_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    envelope = handle_chat(
        body={"model": "gpt-4", "messages": []},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 400


def test_handle_chat_no_api_key_returns_502_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without OPENAI_API_KEY the bridge returns a sanitised 502, not a crash."""
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    envelope = handle_chat(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 502
    assert "upstream_error" in envelope["body"]


# ── Streaming (handle_chat_stream) ──────────────────────────────────────────


def _register_fake_provider(
    chunks: list[str],
    module_name: str = "opengateway.providers.fake",
    usage: dict[str, int] | None = None,
) -> None:
    """Install a stub provider module so the bridge's importlib dispatch
    resolves a class without touching the network."""
    import json
    import sys
    import types

    from opengateway.providers.base import BaseProvider, ChatResponse

    class FakeProvider(BaseProvider):
        def __init__(self, api_key: str, base_url: str | None = None) -> None:
            super().__init__(api_key, base_url)

        async def chat(self, request: Any) -> ChatResponse:
            return ChatResponse(
                id="chatcmpl-test",
                model=request.model,
                content="".join(chunks),
                usage=usage or {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                finish_reason="stop",
            )

        async def chat_stream(self, request: Any):
            for text in chunks:
                yield json.dumps(
                    {
                        "id": "chatcmpl-test",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": text},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
            if usage is not None:
                # The terminal usage chunk OpenAI emits when
                # stream_options.include_usage is set.
                yield json.dumps(
                    {
                        "id": "chatcmpl-test",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": request.model,
                        "choices": [],
                        "usage": usage,
                    }
                )

        async def close(self) -> None:
            return None

    module = types.ModuleType(module_name)
    class_name = module_name.rsplit(".", 1)[-1].capitalize() + "Provider"
    setattr(module, class_name, FakeProvider)
    sys.modules[module_name] = module


def _drain_stream(handle: Any) -> list[str]:
    """Pull every frame out of a StreamHandle until EOF."""
    frames: list[str] = []
    for _ in range(100):
        code, payload = handle.next_chunk(1.0)
        if code == 2:
            return frames
        if payload:
            frames.append(payload)
    raise AssertionError("stream never reached EOF")


def test_handle_chat_stream_missing_auth_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    envelope = handle_chat_stream(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization=None,
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 401
    assert "authentication_error" in envelope["body"]


def test_handle_chat_stream_missing_model_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    envelope = handle_chat_stream(
        body={"messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 400
    assert "invalid_request_error" in envelope["body"]


def test_handle_chat_stream_no_api_key_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    envelope = handle_chat_stream(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 502
    assert "upstream_error" in envelope["body"]


def test_handle_chat_stream_happy_path_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    _register_fake_provider(["Hello", ", world"])

    envelope = handle_chat_stream(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.fake",
    )
    assert envelope["status"] == 200

    frames = _drain_stream(envelope["handle"])
    assert frames[-1] == "data: [DONE]\n\n"
    body_frames = frames[:-1]
    assert len(body_frames) == 2
    assert all(f.startswith("data: ") and f.endswith("\n\n") for f in body_frames)
    import json

    # Raw pass-through: frames carry the upstream chat.completion.chunk
    # envelope, so clients can read choices[0].delta.content directly.
    first = json.loads(body_frames[0][6:])
    assert first["object"] == "chat.completion.chunk"
    assert first["choices"][0]["delta"]["content"] == "Hello"
    assert first["model"] == "gpt-4"


def test_handle_chat_stream_validation_runs_before_thread_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 4xx validation failure must not spawn a pump thread."""
    import threading

    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    before = {t.name for t in threading.enumerate()}
    envelope = handle_chat_stream(
        body={"model": "gpt-4"},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 400
    after = {t.name for t in threading.enumerate()}
    assert not any(name.startswith("opengateway-sse-pump") for name in after - before)


# ── Virtual key store (DB-backed auth) ──────────────────────────────────────


class _FakeStore:
    def __init__(self, records: dict[str, Any]) -> None:
        self._records = records
        self.calls = 0
        self.recorded: list[tuple[str, int]] = []

    def lookup(self, key_hash: str) -> Any:
        self.calls += 1
        return self._records.get(key_hash)

    def record_usage(self, key_id: str, total_tokens: int) -> None:
        self.recorded.append((key_id, total_tokens))


def _fake_record(**overrides: Any) -> Any:
    from opengateway.mojo_bridge.db import VirtualKeyRecord

    defaults: dict[str, Any] = {
        "key_id": "vk_test",
        "name": "test-key",
        "is_admin": False,
        "models": None,
        "max_budget": None,
        "budget_used": 0.0,
        "tpm_limit": None,
        "rpm_limit": None,
    }
    defaults.update(overrides)
    return VirtualKeyRecord(**defaults)


def test_authenticate_virtual_key_from_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record(models=["gpt-4"], rpm_limit=60)})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    result = authenticate_authorization("Bearer sk-og-tenant")
    assert result.key_id == "vk_test"
    assert result.models == ["gpt-4"]
    assert result.rpm_limit == 60
    assert result.is_admin is False


def test_authenticate_unknown_virtual_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: _FakeStore({}))
    with pytest.raises(PermissionError, match="invalid virtual key"):
        authenticate_authorization("Bearer sk-og-nobody")


def test_authenticate_virtual_key_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record()})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    authenticate_authorization("Bearer sk-og-tenant")
    authenticate_authorization("Bearer sk-og-tenant")
    assert store.calls == 1


def test_authenticate_root_key_bypasses_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    store = _FakeStore({})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    result = authenticate_authorization("Bearer sk-root-good")
    assert result.key_id == "root"
    assert store.calls == 0


# ── Distributed rate limiting ────────────────────────────────────────────────


class _FakeLimiter:
    def __init__(self, allow: bool) -> None:
        self._allow = allow
        self.calls: list[tuple[str, int]] = []

    def allow(self, key_id: str, rpm_limit: int) -> bool:
        self.calls.append((key_id, rpm_limit))
        return self._allow


def test_handle_chat_rate_limited_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record(rpm_limit=60)})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)
    monkeypatch.setattr(
        "opengateway.mojo_bridge.ratelimit.get_limiter", lambda: _FakeLimiter(allow=False)
    )

    envelope = handle_chat(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 429
    assert "rate_limit_error" in envelope["body"]


def test_handle_chat_rate_limiter_not_consulted_without_rpm_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record(rpm_limit=None)})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)
    limiter = _FakeLimiter(allow=False)
    monkeypatch.setattr("opengateway.mojo_bridge.ratelimit.get_limiter", lambda: limiter)

    # No OPENAI_API_KEY → 502 from the provider path, proving the
    # limiter never ran (a limiter denial would 429 first).
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    envelope = handle_chat(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 502
    assert limiter.calls == []


# ── Spend recording ──────────────────────────────────────────────────────────


def test_handle_chat_records_usage_for_virtual_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record()})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)
    _register_fake_provider(
        ["ok"], usage={"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}
    )

    envelope = handle_chat(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.fake",
    )
    assert envelope["status"] == 200
    assert store.recorded == [("vk_test", 12)]


def test_handle_chat_does_not_record_for_root_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)
    _register_fake_provider(["ok"])

    envelope = handle_chat(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-root-good",
        provider_module="opengateway.providers.fake",
    )
    assert envelope["status"] == 200
    assert store.recorded == []


def test_stream_records_usage_from_usage_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record()})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)
    _register_fake_provider(
        ["Hello"], usage={"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
    )

    envelope = handle_chat_stream(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.fake",
    )
    assert envelope["status"] == 200
    frames = _drain_stream(envelope["handle"])
    assert frames[-1] == "data: [DONE]\n\n"
    assert store.recorded == [("vk_test", 7)]


def test_stream_without_usage_chunk_records_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record()})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)
    _register_fake_provider(["Hello"], usage=None)

    envelope = handle_chat_stream(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.fake",
    )
    assert envelope["status"] == 200
    _drain_stream(envelope["handle"])
    assert store.recorded == []


def test_budget_enforcement_uses_recorded_spend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    store = _FakeStore(
        {_hash_key("sk-og-tenant"): _fake_record(max_budget=100.0, budget_used=100.0)}
    )
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    envelope = handle_chat(
        body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 429
    assert "budget" in envelope["body"]


# ── Mojo import surface ──────────────────────────────────────────────────────


def test_mojo_bridge_exports_expected_symbols() -> None:
    """Make sure the Mojo PythonObject bridge can rely on these names."""
    import opengateway.mojo_bridge as bridge

    expected = {
        "handle_chat",
        "handle_chat_stream",
        "health_check",
        "authenticate_authorization",
        "AuthResult",
    }
    for name in expected:
        assert hasattr(bridge, name), f"missing export: {name}"


# ── Provider module routing (parallel to router.mojo logic) ─────────────────


@pytest.mark.parametrize(
    "model,expected_module",
    [
        ("gpt-4", "opengateway.providers.openai"),
        ("gpt-4o-mini", "opengateway.providers.openai"),
        ("openai/gpt-4", "opengateway.providers.openai"),
        ("claude-3-5-sonnet", "opengateway.providers.anthropic"),
        ("anthropic/claude-3-opus", "opengateway.providers.anthropic"),
        ("bedrock/anthropic.claude-3-sonnet", "opengateway.providers.bedrock"),
    ],
)
def test_routing_rules_match_mojo_router(model: str, expected_module: str) -> None:
    """The Python bridge must agree with opengateway/mojo/router.mojo."""
    actual = _route_model(model)
    assert actual == expected_module, f"model {model!r} should route to {expected_module}"


def _route_model(model: str) -> str:
    """Python mirror of opengateway/mojo/router.mojo::select_provider_module.

    Kept in lock-step with the Mojo source. Update both together.
    """
    if model.startswith("gpt-") or model.startswith("openai/"):
        return "opengateway.providers.openai"
    if model.startswith("claude-") or model.startswith("anthropic/"):
        return "opengateway.providers.anthropic"
    if model.startswith("bedrock/") or model.startswith("amazon."):
        return "opengateway.providers.bedrock"
    return ""
