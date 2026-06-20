from __future__ import annotations

import secrets
import string

ALPHABET = string.ascii_letters + string.digits
DEFAULT_PREFIX = "sk-og"


def generate_key(prefix: str = DEFAULT_PREFIX, entropy_bytes: int = 32) -> str:
    """Generate a URL-safe API key.

    Format: {prefix}-{token}
    Token is 43 characters of URL-safe base64 (256 bits of entropy).

    Examples:
        >>> generate_key()
        'sk-og-aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890AbCdEf'
        >>> generate_key("pk-og")
        'pk-og-xYzAbCdEfGhIjKlMnOpQrStUvWxYz1234567890Ab'
    """
    token = "".join(secrets.choice(ALPHABET) for _ in range(entropy_bytes))
    return f"{prefix}-{token}"


def generate_test_key() -> str:
    """Generate a key for testing (shorter, clearly marked)."""
    return generate_key(prefix="sk-og-test", entropy_bytes=16)


def is_valid_key_format(key: str, prefix: str = DEFAULT_PREFIX) -> bool:
    """Validate key format without checking the database."""
    if not key.startswith(f"{prefix}-"):
        return False
    token = key[len(prefix) + 1 :]
    if len(token) < 16:
        return False
    return all(c in ALPHABET for c in token)
