from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

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


class BaseProvider:
    """Base class for LLM provider adapters."""

    def __init__(self, api_key: str, base_url: str | None = None, timeout: int = 60) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    async def chat_stream(
        self, request: ChatRequest
    ) -> AsyncGenerator[ChatResponse, None]:
        raise NotImplementedError

    async def close(self) -> None:
        await self._client.aclose()
