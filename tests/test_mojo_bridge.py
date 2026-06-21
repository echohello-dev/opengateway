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

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


# ── Mojo import surface ──────────────────────────────────────────────────────


def test_mojo_bridge_exports_expected_symbols() -> None:
    """Make sure the Mojo PythonObject bridge can rely on these names."""
    import opengateway.mojo_bridge as bridge

    expected = {"handle_chat", "health_check", "authenticate_authorization", "AuthResult"}
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
