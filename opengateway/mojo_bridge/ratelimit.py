"""Distributed rate limiting for the Mojo bridge.

Per-virtual-key fixed-window RPM enforcement backed by Redis. The
Mojo-side ``RateLimit`` middleware (ADR-003 follow-up 3) is a coarse
process-level admission gate; this limiter is the per-key counterpart:
it enforces the ``rpm_limit`` on each virtual key's ``AuthResult``.

Design notes:

- Weighted sliding window (current bucket + previous bucket decayed
  by elapsed fraction), not a naive fixed window. Kills the 2x
  burst-at-window-edge problem at the cost of one extra ``GET`` per
  check; still trivially correct across replicas.
- One connection per check, same one-shot-``asyncio.run`` rationale as
  the virtual key store (see ``db.py``'s module docstring).
- Fail-open: if Redis is unreachable the request is admitted and a
  warning is logged. A rate limiter that takes the gateway down with
  it is worse than none.
- Disabled when ``redis_url`` is unset or the key has no ``rpm_limit``.

Testability seam: ``get_limiter`` is the single construction point;
tests monkeypatch it with an in-memory fake.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Protocol

logger = logging.getLogger("opengateway.mojo_bridge.ratelimit")

_limiter: RateLimiter | None = None
_limiter_initialised = False


class RateLimiter(Protocol):
    """Per-key admission check seam."""

    def allow(self, key_id: str, rpm_limit: int) -> bool:
        """Return True if the request may proceed under ``rpm_limit``."""
        ...


class RedisRateLimiter:
    """Weighted sliding-window per-key RPM via Redis."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    def allow(self, key_id: str, rpm_limit: int) -> bool:
        try:
            return asyncio.run(self._allow(key_id, rpm_limit))
        except Exception:
            logger.warning("redis rate-limit check failed; admitting request", exc_info=True)
            return True

    async def _allow(self, key_id: str, rpm_limit: int) -> bool:
        import redis.asyncio as redis

        client = redis.from_url(self._redis_url)
        try:
            now = time.time()
            window = int(now // 60)
            elapsed_fraction = (now % 60) / 60.0

            curr_bucket = f"opengateway:ratelimit:{key_id}:{window}"
            prev_bucket = f"opengateway:ratelimit:{key_id}:{window - 1}"

            prev_raw = await client.get(prev_bucket)
            prev_count = int(prev_raw) if prev_raw else 0
            curr_count = await client.incr(curr_bucket)
            if curr_count == 1:
                await client.expire(curr_bucket, 120)

            estimated = prev_count * (1.0 - elapsed_fraction) + curr_count
            return bool(estimated <= rpm_limit)
        finally:
            await client.aclose()


def get_limiter() -> RateLimiter | None:
    """Return the configured limiter, or ``None`` when Redis is unset."""
    global _limiter, _limiter_initialised
    if _limiter_initialised:
        return _limiter
    _limiter_initialised = True

    from opengateway.config import get_settings

    url = get_settings().redis_url
    if not url:
        logger.info("no redis_url configured; distributed rate limiting disabled")
        _limiter = None
        return None
    logger.info("rate limiter: redis fixed-window")
    _limiter = RedisRateLimiter(str(url))
    return _limiter


def reset_limiter_cache() -> None:
    """Drop the cached limiter. Used by tests after monkeypatching settings."""
    global _limiter, _limiter_initialised
    _limiter = None
    _limiter_initialised = False
