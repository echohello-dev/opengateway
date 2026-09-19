"""Tests for the per-virtual-key dollar cost cap (issue #4).

The cap is enforced *before* the upstream call. The estimate is an
upper bound (worst-case ``max_tokens`` × output price + prompt
estimate × input price); over-estimation is the right bias for a cap.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from opengateway.mojo_bridge import handle_chat, handle_chat_stream
from opengateway.mojo_bridge.auth import _hash_key


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
        "model": "gpt-4o-mini",
        "primary": "openai",
        "input_price_per_1k": 0.00015,
        "output_price_per_1k": 0.0006,
        "max_output_tokens": 16384,
    }
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


def test_cost_cap_rejects_when_estimate_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """max_tokens × output_price > max_cost_usd ⇒ 429."""
    _set_routes(monkeypatch)
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record(max_cost_usd=0.01)})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    envelope = handle_chat(
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            # 16384 output tokens × $0.0006 / 1k = $0.00983 > $0.01 cap.
            # Wait, $0.00983 < $0.01, bump max_tokens to push over the cap.
            "max_tokens": 20000,
        },
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 429
    assert "cost budget exceeded" in envelope["body"]
    assert "max_cost_usd" in envelope["body"]


def test_cost_cap_allows_under_limit_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Small request under the cap succeeds."""
    from opengateway.providers.base import BaseProvider, ChatResponse

    class _FakeProvider(BaseProvider):
        async def chat(self, request: Any) -> ChatResponse:
            return ChatResponse(
                id="chatcmpl-cost",
                model=request.model,
                content="ok",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                finish_reason="stop",
            )

        async def chat_stream(self, request: Any):  # pragma: no cover - unused
            if False:
                yield ""

        async def close(self) -> None:
            return None

    # Swap the openai module's provider class with our fake via
    # monkeypatch so the swap is automatically reverted at end of
    # test. This prevents pollution into the next test, which relies
    # on the real OpenAIProvider raising a real network error.
    import opengateway.providers.openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAIProvider", _FakeProvider)

    _set_routes(monkeypatch)
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record(max_cost_usd=10.0)})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    envelope = handle_chat(
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 50,
        },
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 200


def test_cost_cap_skipped_when_no_route_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a route entry the estimate is unavailable; skip the cap.

    The pre-#4 behaviour (no routes, no cap) must still work.
    """
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("ROUTES_JSON", raising=False)
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record(max_cost_usd=0.0001)})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    envelope = handle_chat(
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 20000,
        },
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    # No route → no cap enforcement → falls through to the no-API-key
    # 502 path, proving the cap was *not* the reason for rejection.
    assert envelope["status"] == 502


def test_cost_cap_skipped_when_key_has_no_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_routes(monkeypatch)
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record(max_cost_usd=None)})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    envelope = handle_chat(
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 20000,
        },
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    # No cap on key → cap is not enforced; request proceeds to the
    # provider path (502 because the provider raises for the fake
    # model). The cap MUST NOT be the reason for rejection.
    assert envelope["status"] == 502


def test_cost_cap_enforced_on_streaming_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_routes(monkeypatch)
    monkeypatch.setenv("ROOT_KEY", "sk-root-good")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    store = _FakeStore({_hash_key("sk-og-tenant"): _fake_record(max_cost_usd=0.01)})
    monkeypatch.setattr("opengateway.mojo_bridge.db.get_store", lambda: store)

    envelope = handle_chat_stream(
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "max_tokens": 20000,
        },
        authorization="Bearer sk-og-tenant",
        provider_module="opengateway.providers.openai",
    )
    assert envelope["status"] == 429
    assert "cost budget exceeded" in envelope["body"]


def test_root_key_has_no_cost_cap() -> None:
    """Sanity: the AuthResult default for the root key sets max_cost_usd=None."""
    from opengateway.config import get_settings
    from opengateway.mojo_bridge.auth import authenticate_authorization

    get_settings.cache_clear()
    from opengateway.mojo_bridge import auth as bridge_auth

    bridge_auth._cache.clear()

    result = authenticate_authorization("Bearer sk-root-change-me")
    assert result.max_cost_usd is None
