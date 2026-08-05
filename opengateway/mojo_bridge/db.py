"""Virtual key persistence for the Mojo bridge.

The Mojo layer never talks to Postgres directly; auth goes through
``authenticate_authorization`` in ``opengateway.mojo_bridge.auth``,
which consults a ``VirtualKeyStore`` after the root-key short-circuit.

The bridge is synchronous (one-shot ``asyncio.run`` per request), so
the store opens a fresh connection per lookup instead of holding a
pool — a pool cannot outlive the event loop that created it. At LLM
gateway latencies (upstream calls dominate by orders of magnitude)
the per-request connect cost is noise, and the auth TTL cache absorbs
repeat lookups for the same key. A pooled store is a follow-up if the
connect cost ever shows up in a profile.

Testability seam: ``get_store`` is the single construction point;
tests monkeypatch it with an in-memory fake.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("opengateway.mojo_bridge.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS virtual_keys (
    key_id      TEXT PRIMARY KEY,
    key_hash    TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL DEFAULT '',
    team_id     TEXT,
    org_id      TEXT,
    is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
    models      JSONB,
    max_budget  DOUBLE PRECISION,
    budget_used DOUBLE PRECISION NOT NULL DEFAULT 0,
    tpm_limit   INTEGER,
    rpm_limit   INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);
"""

_LOOKUP_SQL = """
SELECT key_id, name, is_admin, models, max_budget, budget_used,
       tpm_limit, rpm_limit
FROM virtual_keys
WHERE key_hash = $1 AND revoked_at IS NULL;
"""


@dataclass(frozen=True, slots=True)
class VirtualKeyRecord:
    """One row of the ``virtual_keys`` table."""

    key_id: str
    name: str
    is_admin: bool
    models: list[str] | None
    max_budget: float | None
    budget_used: float
    tpm_limit: int | None
    rpm_limit: int | None


class VirtualKeyStore(Protocol):
    """Lookup seam for virtual key records."""

    def lookup(self, key_hash: str) -> VirtualKeyRecord | None:
        """Return the record for ``key_hash``, or ``None`` if unknown
        or revoked."""
        ...


class PostgresVirtualKeyStore:
    """asyncpg-backed store. One connection per lookup (see module docstring)."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def lookup(self, key_hash: str) -> VirtualKeyRecord | None:
        return asyncio.run(self._lookup(key_hash))

    async def _lookup(self, key_hash: str) -> VirtualKeyRecord | None:
        import asyncpg

        conn = await asyncpg.connect(self._database_url)
        try:
            await conn.execute("SELECT 1")  # fail fast on bad credentials
            row = await conn.fetchrow(_LOOKUP_SQL, key_hash)
        finally:
            await conn.close()
        if row is None:
            return None
        return VirtualKeyRecord(
            key_id=row["key_id"],
            name=row["name"],
            is_admin=row["is_admin"],
            models=list(row["models"]) if row["models"] is not None else None,
            max_budget=row["max_budget"],
            budget_used=row["budget_used"],
            tpm_limit=row["tpm_limit"],
            rpm_limit=row["rpm_limit"],
        )

    async def ensure_schema(self) -> None:
        import asyncpg

        conn = await asyncpg.connect(self._database_url)
        try:
            await conn.execute(_SCHEMA)
        finally:
            await conn.close()


_store: VirtualKeyStore | None = None
_store_initialised = False


def get_store() -> VirtualKeyStore | None:
    """Return the configured store, or ``None`` when no database is set.

    Cached after first call. ``None`` means the deployment is
    root-key-only — the auth layer skips the DB path entirely.
    """
    global _store, _store_initialised
    if _store_initialised:
        return _store
    _store_initialised = True

    from opengateway.config import get_settings

    url = get_settings().database_url
    if not url:
        logger.info("no database_url configured; virtual key store disabled")
        _store = None
        return None
    logger.info("virtual key store: postgres")
    _store = PostgresVirtualKeyStore(str(url))
    return _store


def reset_store_cache() -> None:
    """Drop the cached store. Used by tests after monkeypatching settings."""
    global _store, _store_initialised
    _store = None
    _store_initialised = False
