"""Auth entry point callable from Mojo.

Validates the Authorization header and returns a serialisable auth
result that the Mojo handler can pass back to the Python provider
stack.

Lookup order:

1. Root key match (constant-time-ish hash compare) — always available,
   no I/O.
2. Virtual key store (Postgres, when ``database_url`` is configured) —
   looked up by key hash, cached in-process for ``_CACHE_TTL_S``.
3. Anything else raises ``PermissionError``.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from typing import Any

from opengateway.config import get_settings

_CACHE_TTL_S = 60.0


@dataclass(frozen=True, slots=True)
class AuthResult:
    key_id: str
    name: str
    is_admin: bool
    models: list[str] | None
    max_budget: float | None
    budget_used: float
    tpm_limit: int | None
    rpm_limit: int | None


# key_hash -> (AuthResult, expires_at). In-process only; revocation
# may take up to _CACHE_TTL_S to propagate. Bounded by distinct-key
# cardinality, which is operator-controlled.
_cache: dict[str, tuple[AuthResult, float]] = {}


def authenticate_authorization(authorization: str | None) -> AuthResult:
    """Validate the Authorization header.

    Returns the root AuthResult when the bearer matches the configured
    root key; otherwise consults the virtual key store (when
    configured). Raises PermissionError for any failure.
    """
    settings = get_settings()

    token = _extract_bearer(authorization)
    if token is None:
        raise PermissionError("missing or malformed authorization header")

    key_hash = _hash_key(token)

    if key_hash == _hash_key(settings.root_key):
        return AuthResult(
            key_id="root",
            name="root",
            is_admin=True,
            models=None,
            max_budget=None,
            budget_used=0.0,
            tpm_limit=None,
            rpm_limit=None,
        )

    record = _lookup_virtual_key(key_hash)
    if record is None:
        raise PermissionError("invalid virtual key")
    return record


def auth_result_to_dict(auth: AuthResult) -> dict[str, Any]:
    return asdict(auth)


def _lookup_virtual_key(key_hash: str) -> AuthResult | None:
    cached = _cache.get(key_hash)
    if cached is not None and cached[1] > time.monotonic():
        return cached[0]

    from opengateway.mojo_bridge.db import get_store

    store = get_store()
    if store is None:
        return None
    record = store.lookup(key_hash)
    if record is None:
        return None

    result = AuthResult(
        key_id=record.key_id,
        name=record.name,
        is_admin=record.is_admin,
        models=record.models,
        max_budget=record.max_budget,
        budget_used=record.budget_used,
        tpm_limit=record.tpm_limit,
        rpm_limit=record.rpm_limit,
    )
    _cache[key_hash] = (result, time.monotonic() + _CACHE_TTL_S)
    return result


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    lower = authorization.lower()
    if not lower.startswith("bearer "):
        return None
    return authorization[7:].strip() or None


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:32]
