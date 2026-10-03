"""Suite-wide test hermeticity.

``Settings`` loads ``.env`` from the CWD and reads the process
environment. Left alone, a developer's local ``.env`` (or exported
vars) silently leaks into tests and changes gateway behaviour — the
same class of bug as issue #46. This fixture points the CWD at a
per-test tmp dir and strips gateway env vars so every test starts
from documented defaults and sets exactly what it needs via
``monkeypatch.setenv`` (process env takes precedence over ``.env``
in pydantic-settings).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from opengateway.config import get_settings

_GATEWAY_ENV_VARS = (
    "ROOT_KEY",
    "REQUIRE_AUTH",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_BASE_URL",
    "ROUTES_JSON",
    "DATABASE_URL",
    "REDIS_URL",
)


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)
    for var in _GATEWAY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
