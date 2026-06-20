from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from opengateway.providers.base import BaseProvider, ChatRequest, ChatResponse

logger = structlog.get_logger()


class OpenAIProvider(BaseProvider):
    """OpenAI-compatible provider adapter."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, api_key: str, base_url: str | None = None, timeout: int = 60) -> None:
        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, timeout)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat completion request to OpenAI."""
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        payload.update(request.extra)

        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})
        return ChatResponse(
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
            model=data.get("model", request.model),
            content=choice["message"]["content"],
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            finish_reason=choice.get("finish_reason"),
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[ChatResponse, None]:
        """Send a streaming chat completion request to OpenAI."""
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        payload.update(request.extra)

        async with self._client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json

                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield ChatResponse(
                                id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
                                model=data.get("model", request.model),
                                content=content,
                                usage={},
                                finish_reason=data["choices"][0].get("finish_reason"),
                            )
                    except json.JSONDecodeError:
                        continue
