"""Python bridge for the Mojo API surface.

The Mojo HTTP server (opengateway.mojo.main) calls into these synchronous
entry points. The non-streaming path owns a one-shot asyncio event loop
that drives the existing async provider code unchanged; the streaming
path spawns a background pump thread per request that feeds SSE frames
into a bounded queue the Mojo reactor drains.

Public surface (called from Mojo via ``Python.import_module``):

- ``handle_chat(body, authorization, provider_module)``: envelope wrapper
  around :func:`chat_completion` returning ``{"status", "body"}`` so the
  Mojo layer never has to catch Python exceptions.
- ``handle_chat_stream(body, authorization, provider_module)``: streaming
  variant returning ``{"status": 200, "handle": StreamHandle}`` on
  success; validation failures return the same error envelope shape as
  ``handle_chat``.
- ``health_check()``: static dict for the ``/health`` route.
- ``authenticate_authorization(authorization)``: root-key validation.
"""

from __future__ import annotations

import logging
from typing import Any

from opengateway.mojo_bridge.auth import AuthResult, authenticate_authorization
from opengateway.mojo_bridge.chat import chat_completion, health_check
from opengateway.mojo_bridge.stream import start_streaming_chat
from opengateway.mojo_bridge.tls_proxy import start_tls_proxy

__all__ = [
    "handle_chat",
    "handle_chat_stream",
    "health_check",
    "authenticate_authorization",
    "AuthResult",
    "start_tls_proxy",
]

logger = logging.getLogger("opengateway.mojo_bridge")


def handle_chat(
    body: dict[str, Any],
    authorization: str | None,
    provider_module: str,
) -> dict[str, Any]:
    """Drive a chat completion request synchronously, returning an envelope.

    The envelope shape is ``{"status": <int>, "body": <json str>}`` so the
    Mojo handler can map ``status`` to an HTTP response code without
    catching Python exceptions itself. Errors are mapped as follows:

    - ``PermissionError`` (missing/invalid auth, model not allowed, budget):
      401 / 403 / 429.
    - ``ValueError`` (missing fields, unknown model): 400.
    - ``RuntimeError`` (upstream failure): 502.
    - Any other exception: 500.
    """
    try:
        result = chat_completion(body, authorization, provider_module)
        return {"status": 200, "body": _json_dumps(result)}
    except Exception as exc:
        return _map_exception(exc)


def handle_chat_stream(
    body: dict[str, Any],
    authorization: str | None,
    provider_module: str,
) -> dict[str, Any]:
    """Validate a streaming request and start the SSE pump thread.

    Returns ``{"status": 200, "handle": StreamHandle}`` on success; the
    Mojo handler wraps the handle in a ``ChunkSource`` and serves it via
    ``stream_response``. Validation failures return the same
    ``{"status", "body"}`` envelope shape as :func:`handle_chat` so the
    handler can respond with a plain (non-SSE) error.
    """
    try:
        return start_streaming_chat(body, authorization, provider_module)
    except Exception as exc:
        return _map_exception(exc)


def _map_exception(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, PermissionError):
        msg = str(exc)
        lower = msg.lower()
        if "rate limit" in lower or "budget" in lower:
            return {"status": 429, "body": _error_body("rate_limit_error", msg)}
        if "model" in lower:
            return {"status": 403, "body": _error_body("permission_error", msg)}
        return {"status": 401, "body": _error_body("authentication_error", msg)}
    if isinstance(exc, ValueError):
        return {"status": 400, "body": _error_body("invalid_request_error", str(exc))}
    if isinstance(exc, RuntimeError):
        logger.exception("upstream provider failure")
        return {"status": 502, "body": _error_body("upstream_error", "upstream provider error")}
    logger.exception("unhandled error in mojo bridge")
    return {"status": 500, "body": _error_body("internal_error", "internal error")}


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj)


def _error_body(kind: str, message: str) -> str:
    import json

    return json.dumps({"error": {"message": message, "type": kind}})
