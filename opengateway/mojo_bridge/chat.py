"""Chat completion entry point callable from Mojo.

Synchronous wrapper around the async provider layer. Returns a JSON-serialisable
dict that the Mojo handler passes back through the bridge envelope.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any

from opengateway.config import get_settings
from opengateway.mojo_bridge.auth import AuthResult, authenticate_authorization
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
    _enforce_model_access(auth, body["model"])
    _enforce_budget(auth)

    return asyncio.run(_run_completion(body, provider_module))


async def _run_completion(body: dict[str, Any], provider_module: str) -> dict[str, Any]:
    settings = get_settings()
    api_key = _resolve_provider_api_key(settings, body["model"])
    if not api_key:
        raise RuntimeError(f"no API key configured for model {body['model']}")

    provider_cls = _load_provider_class(provider_module)
    provider = provider_cls(api_key=api_key)
    try:
        request = _to_chat_request(body)
        response = await provider.chat(request)
    finally:
        await provider.close()

    return _to_openai_response(response)


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
    if auth.max_budget is not None and auth.budget_used >= auth.max_budget:
        raise PermissionError("budget exceeded")


def _to_chat_request(body: dict[str, Any]) -> ChatRequest:
    return ChatRequest(
        model=body["model"],
        messages=body["messages"],
        temperature=body.get("temperature"),
        max_tokens=body.get("max_tokens"),
        top_p=body.get("top_p"),
        stream=False,
        extra={
            k: v
            for k, v in body.items()
            if k not in {"model", "messages", "temperature", "max_tokens", "top_p", "stream"}
        },
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


def _resolve_provider_api_key(settings: Any, model: str) -> str | None:
    if model.startswith("gpt-") or model.startswith("openai/"):
        return settings.openai_api_key or None
    if model.startswith("claude-") or model.startswith("anthropic/"):
        return settings.anthropic_api_key or None
    return settings.openai_api_key or None


def _load_provider_class(provider_module: str) -> Any:
    module = importlib.import_module(provider_module)
    cls = getattr(module, _provider_class_name(provider_module), None)
    if cls is None:
        raise RuntimeError(f"provider module {provider_module} has no provider class")
    return cls


def _provider_class_name(provider_module: str) -> str:
    base = provider_module.rsplit(".", 1)[-1]
    return base[0].upper() + base[1:] + "Provider"
