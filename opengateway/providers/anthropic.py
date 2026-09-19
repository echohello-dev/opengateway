"""Anthropic provider adapter (issue #4 stub).

The bridge resolves ``fallback: anthropic`` to this module. The
OpenAI-compatible ``/v1/messages`` endpoint is the canonical target,
so for v1 the adapter reuses the same httpx plumbing as
:mod:`opengateway.providers.openai` with a different ``base_url``.

Real Anthropic SDK integration (``anthropic-python``) is a follow-up;
the OpenAI-compatible surface is sufficient for the fallback story
and avoids adding a second SDK dependency to the bridge.
"""

from __future__ import annotations

from opengateway.providers.base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Anthropic adapter hitting the OpenAI-compatible ``/v1/messages`` endpoint."""

    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"

    def __init__(self, api_key: str, base_url: str | None = None, timeout: int = 60) -> None:
        super().__init__(api_key, base_url or self.DEFAULT_BASE_URL, timeout)
