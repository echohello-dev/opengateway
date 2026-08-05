"""Streaming chat completion entry point callable from Mojo.

The Mojo ``/v1/chat/completions`` handler calls ``start_streaming_chat``
for requests with ``stream: true``. Validation (auth, model access,
budget) runs synchronously on the calling thread so a bad request
fails before any SSE headers are written; only the upstream HTTP call
moves to a background thread.

The background thread drives the async provider's ``chat_stream``
generator and pushes OpenAI-shaped SSE frames (``data: {...}\\n\\n``)
into a bounded queue. The Mojo side pulls frames through
``next_chunk`` from a ``ChunkSource`` struct, one frame per writable
edge; the queue's ``maxsize`` couples upstream reads to downstream
drain, so a slow client pauses the provider stream instead of growing
memory without bound.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from typing import Any

from opengateway.config import get_settings
from opengateway.mojo_bridge.auth import authenticate_authorization
from opengateway.mojo_bridge.chat import (
    _enforce_budget,
    _enforce_model_access,
    _load_provider_class,
    _resolve_provider_api_key,
    _resolve_provider_base_url,
    _to_chat_request,
    _validate_request,
)

logger = logging.getLogger("opengateway.mojo_bridge.stream")

# Chunk protocol between the Python pump thread and the Mojo
# ``ChunkSource``: next_chunk returns (code, payload) where code is
# _DATA with a frame string, or _EOF with an empty payload.
_DATA = 0
_EOF = 2

_QUEUE_MAXSIZE = 64
_DONE_FRAME = "data: [DONE]\n\n"


class StreamHandle:
    """One in-flight streaming chat completion.

    The Mojo layer holds this as an opaque ``PythonObject`` and calls
    ``next_chunk`` / ``cancel`` on it. All coordination is through the
    bounded queue plus the cancel event; no shared mutable state.
    """

    def __init__(
        self,
        body: dict[str, Any],
        provider_module: str,
        api_key: str,
        base_url: str | None = None,
    ) -> None:
        self._body = body
        self._provider_module = provider_module
        self._api_key = api_key
        self._base_url = base_url
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
            asyncio.run(self._run())
        except Exception:
            logger.exception("streaming pump crashed before event loop start")
        finally:
            self._offer(None)

    async def _run(self) -> None:
        provider_cls = _load_provider_class(self._provider_module)
        provider = provider_cls(api_key=self._api_key, base_url=self._base_url)
        try:
            request = _to_chat_request(self._body, stream=True)
            async for chunk in provider.chat_stream(request):
                if self._cancel.is_set():
                    return
                self._offer(f"data: {chunk.model_dump_json()}\n\n")
            self._offer(_DONE_FRAME)
        except Exception:
            logger.exception("upstream streaming failure")
            if not self._cancel.is_set():
                self._offer(_DONE_FRAME)
        finally:
            await provider.close()

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
    _enforce_budget(auth)

    settings = get_settings()
    api_key = _resolve_provider_api_key(settings, body["model"])
    if not api_key:
        raise RuntimeError(f"no API key configured for model {body['model']}")

    handle = StreamHandle(
        body,
        provider_module,
        api_key,
        base_url=_resolve_provider_base_url(settings, body["model"]),
    )
    handle.start()
    return {"status": 200, "handle": handle}
