from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Normalised chat completion request."""

    model: str
    messages: list[dict[str, Any]]
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Normalised chat completion response."""

    id: str
    model: str
    content: str
    usage: dict[str, int]
    finish_reason: str | None = None

    def model_dump_json(self) -> str:
        return json.dumps(
            {
                "id": self.id,
                "model": self.model,
                "content": self.content,
                "usage": self.usage,
                "finish_reason": self.finish_reason,
            }
        )


class BaseProvider:
    """Base class for LLM provider adapters."""

    def __init__(self, api_key: str, base_url: str | None = None, timeout: int = 60) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[ChatResponse, None]:
        raise NotImplementedError
        yield  # type: ignore[unreachable]  # pragma: no cover - makes this an async generator

    async def close(self) -> None:
        await self._client.aclose()
