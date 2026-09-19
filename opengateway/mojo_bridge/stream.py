"""Streaming chat completion entry point callable from Mojo.

The Mojo ``/v1/chat/completions`` handler calls ``start_streaming_chat``
for requests with ``stream: true``. Validation (auth, model access,
budget, cost cap) runs synchronously on the calling thread so a bad
request fails before any SSE headers are written; only the upstream
HTTP call moves to a background thread.

The background thread drives the async provider's ``chat_stream``
generator and pushes OpenAI-shaped SSE frames (``data: {...}\\n\\n``)
into a bounded queue. The Mojo side pulls frames through
``next_chunk`` from a ``ChunkSource`` struct, one frame per writable
edge; the queue's ``maxsize`` couples upstream reads to downstream
drain, so a slow client pauses the provider stream instead of growing
memory without bound.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

from opengateway.mojo_bridge.auth import authenticate_authorization
from opengateway.mojo_bridge.chat import (
    _enforce_budget,
    _enforce_cost_cap,
    _enforce_model_access,
    _enforce_rate_limit,
    _validate_request,
)
from opengateway.mojo_bridge.db import record_usage_for
from opengateway.mojo_bridge.routing import (
    StreamFallbackError,
    chat_stream_with_fallback,
    resolve_route,
)

logger = logging.getLogger("opengateway.mojo_bridge.stream")

# Chunk protocol between the Python pump thread and the Mojo
# ``ChunkSource``: next_chunk returns (code, payload) where code is
# _DATA with a frame string, or _EOF with an empty payload.
_DATA = 0
_EOF = 2

_QUEUE_MAXSIZE = 64
_DONE_FRAME = "data: [DONE]\n\n"


def _extract_total_tokens(chunk: str) -> int:
    """Pull ``usage.total_tokens`` out of a raw SSE chunk payload.

    Returns 0 when the chunk carries no usage object (every chunk
    except the final one, when ``stream_options.include_usage`` is
    set). Parse failures are treated as no-usage — the frame must
    flow to the client regardless.
    """
    if '"usage"' not in chunk:
        return 0
    import json

    try:
        usage = json.loads(chunk).get("usage")
    except json.JSONDecodeError:
        return 0
    if not usage:
        return 0
    return int(usage.get("total_tokens", 0))


class StreamHandle:
    """One in-flight streaming chat completion.

    The Mojo layer holds this as an opaque ``PythonObject`` and calls
    ``next_chunk`` / ``cancel`` on it. All coordination is through the
    bounded queue plus the cancel event; no shared mutable state.

    The provider path is resolved at construction time via the routing
    table so the pump thread doesn't re-resolve on every chunk.
    """

    def __init__(
        self,
        body: dict[str, Any],
        primary_module: str,
        fallback_module: str | None,
        key_id: str = "",
    ) -> None:
        self._body = body
        self._primary_module = primary_module
        self._fallback_module = fallback_module
        self._key_id = key_id
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._cancel = threading.Event()

    # ── Mojo-facing surface ──────────────────────────────────────────

    def next_chunk(self, timeout_s: float) -> tuple[int, str]:
        """Block up to ``timeout_s`` for the next SSE frame.

        Returns:
            ``(_DATA, frame)`` when a frame is ready, or ``(_EOF, "")``
            once the stream is complete. A timeout returns
            ``(_DATA, "")``; the Mojo caller loops and re-checks its
            cancel token, so a stalled upstream cannot wedge the
            reactor.
        """
        try:
            item = self._queue.get(timeout=timeout_s)
        except queue.Empty:
            return (_DATA, "")
        if item is None:
            return (_EOF, "")
        return (_DATA, item)

    def cancel(self) -> None:
        """Signal the pump thread to stop producing frames.

        Called by the Mojo ``ChunkSource`` when the client disconnects
        or the request deadline fires. Best-effort: the pump checks the
        event between frames and inside its queue-put retry loop.
        """
        self._cancel.set()

    # ── Pump thread ──────────────────────────────────────────────────

    def start(self) -> None:
        thread = threading.Thread(
            target=self._pump,
            name="opengateway-sse-pump",
            daemon=True,
        )
        thread.start()

    def _pump(self) -> None:
        try:
            import asyncio

            asyncio.run(self._run())
        except Exception:
            logger.exception("streaming pump crashed before event loop start")
        finally:
            self._offer(None)

    async def _run(self) -> None:
        total_tokens = 0
        try:
            async for chunk in chat_stream_with_fallback(
                self._body,
                primary_module=self._primary_module,
                fallback_module=self._fallback_module,
                cancel=self._cancel,
            ):
                total_tokens = _extract_total_tokens(chunk) or total_tokens
                self._offer(f"data: {chunk}\n\n")
            self._offer(_DONE_FRAME)
        except StreamFallbackError as exc:
            logger.warning(
                "streaming failed before any frame could be served",
                extra={
                    "primary": self._primary_module,
                    "fallback": self._fallback_module,
                    "on_fallback": exc.on_fallback,
                },
                exc_info=exc.original,
            )
            # We've already committed to a stream response, so we
            # can't switch to a JSON error envelope. Close the stream
            # cleanly with the canonical terminator and let the
            # client surface the truncation. (Streaming providers
            # that error after frames are already sent are handled the
            # same way — see the catch-all in the helper.)
            if not self._cancel.is_set():
                self._offer(_DONE_FRAME)
        except Exception:
            logger.exception("upstream streaming failure")
            if not self._cancel.is_set():
                self._offer(_DONE_FRAME)
        finally:
            if not self._cancel.is_set():
                record_usage_for(self._key_id, total_tokens)

    def _offer(self, item: str | None, deadline_s: float = 2.0) -> None:
        """Put ``item`` on the queue with backpressure, respecting cancel.

        Blocks while the queue is full (that *is* the backpressure: a
        slow client stops the pump, which stops the upstream read).
        Gives up after ``deadline_s`` so a cancelled stream can never
        leak the thread.
        """
        deadline = time.monotonic() + deadline_s
        while time.monotonic() < deadline:
            if self._cancel.is_set() and item is not None:
                return
            try:
                self._queue.put(item, timeout=0.05)
                return
            except queue.Full:
                continue


def start_streaming_chat(
    body: dict[str, Any],
    authorization: str | None,
    provider_module: str,
) -> dict[str, Any]:
    """Validate a streaming request and start the pump thread.

    Raises the same exceptions as :func:`chat_completion` (mapped to
    error envelopes by :func:`handle_chat_stream` in the package
    ``__init__``), so the Mojo handler can return a non-SSE error
    response before any streaming headers are emitted.
    """
    auth = authenticate_authorization(authorization)
    _validate_request(body)
    _enforce_model_access(auth, body["model"])
    route, resolved_primary = resolve_route(body["model"], default_module=provider_module)
    _enforce_budget(auth)
    _enforce_cost_cap(auth, route, body)
    _enforce_rate_limit(auth)

    # Pre-flight the primary provider's API key. Without this, the
    # pump thread would fail after we've already returned
    # ``{"status": 200, "handle": ...}``, leaving the Mojo layer
    # committed to a 200 stream with no way to surface the missing-
    # key error. The bridge maps ``RuntimeError`` to 502.
    #
    # Only enforced for modules with a registered API key field
    # (``openai``, ``anthropic``); custom adapters and test stubs are
    # allowed to operate without one — their own ``chat_stream``
    # implementations can decide how to handle a missing key.
    from opengateway.mojo_bridge.routing import (
        _PROVIDER_MODULE_TO_SETTINGS_API_KEY,
        resolve_provider_api_key,
    )

    if resolved_primary in _PROVIDER_MODULE_TO_SETTINGS_API_KEY and not resolve_provider_api_key(
        resolved_primary
    ):
        raise RuntimeError(f"no API key configured for provider {resolved_primary}")

    fallback_module = (
        _routing_module_name(route.fallback)
        if route is not None and route.fallback
        else None
    )
    if (
        fallback_module is not None
        and fallback_module in _PROVIDER_MODULE_TO_SETTINGS_API_KEY
        and not resolve_provider_api_key(fallback_module)
    ):
        raise RuntimeError(f"no API key configured for fallback provider {fallback_module}")

    handle = StreamHandle(
        body,
        primary_module=resolved_primary,
        fallback_module=fallback_module,
        key_id=auth.key_id,
    )
    handle.start()
    return {"status": 200, "handle": handle}


def _routing_module_name(provider: str) -> str:
    if "." in provider:
        return provider
    return f"opengateway.providers.{provider}"
