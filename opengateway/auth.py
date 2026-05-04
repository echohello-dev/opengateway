from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any

import redis.asyncio as redis
import structlog
from fastapi import HTTPException, Request

logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class VirtualKey:
    """Represents an authenticated virtual key with its permissions."""

    key_hash: str
    key_id: str
    team_id: str | None
    org_id: str | None
    name: str | None
    is_admin: bool
    models: list[str] | None
    max_budget: float | None
    budget_used: float
    tpm_limit: int | None
    rpm_limit: int | None
    metadata: dict[str, Any]

    def has_model_access(self, model: str) -> bool:
        if self.models is None:
            return True
        return model in self.models

    def is_within_budget(self) -> bool:
        if self.max_budget is None:
            return True
        return self.budget_used < self.max_budget


class AuthService:
    """Handles virtual key authentication with Redis caching."""

    def __init__(self, master_key: str, redis_client: redis.Redis | None = None) -> None:
        self.master_key = master_key
        self.master_key_hash = self._hash_key(master_key)
        self._redis = redis_client
        self._local_cache: dict[str, VirtualKey] = {}

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash a key for storage and lookup comparison."""
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def _extract_bearer(self, request: Request) -> str | None:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return None

    async def authenticate(self, request: Request) -> VirtualKey:
        """Authenticate a request and return the virtual key details."""
        token = self._extract_bearer(request)
        if not token:
            raise HTTPException(status_code=401, detail="Missing authorization header")

        key_hash = self._hash_key(token)

        # Check master key first
        if key_hash == self.master_key_hash:
            return VirtualKey(
                key_hash=key_hash,
                key_id="master",
                team_id=None,
                org_id=None,
                name="master",
                is_admin=True,
                models=None,
                max_budget=None,
                budget_used=0.0,
                tpm_limit=None,
                rpm_limit=None,
                metadata={},
            )

        # Check local cache
        if key_hash in self._local_cache:
            vk = self._local_cache[key_hash]
            if not vk.is_within_budget():
                raise HTTPException(status_code=429, detail="Budget exceeded")
            return vk

        # In a real implementation, this would query PostgreSQL and cache in Redis.
        # For the minimal version, we use an in-memory fallback.
        # TODO: implement DB lookup with Redis caching

        raise HTTPException(status_code=401, detail="Invalid virtual key")
