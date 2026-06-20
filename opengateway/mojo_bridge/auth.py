"""Auth entry point callable from Mojo.

Validates the Authorization header against the configured root key and returns
a serialisable auth result that the Mojo handler can pass back to the Python
provider stack.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from opengateway.config import get_settings


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


def authenticate_authorization(authorization: str | None) -> AuthResult:
    """Validate the Authorization header.

    Returns the root AuthResult when the bearer matches the configured root key.
    Raises PermissionError for any other case (missing header, wrong scheme, bad key).
    Future DB-backed lookups will check virtual keys before falling through to
    the root key bypass.
    """
    settings = get_settings()

    token = _extract_bearer(authorization)
    if token is None:
        raise PermissionError("missing or malformed authorization header")

    if _hash_key(token) == _hash_key(settings.root_key):
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

    raise PermissionError("invalid virtual key")


def auth_result_to_dict(auth: AuthResult) -> dict[str, Any]:
    return asdict(auth)


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    lower = authorization.lower()
    if not lower.startswith("bearer "):
        return None
    return authorization[7:].strip() or None


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:32]
