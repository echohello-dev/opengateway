# Contributing to OpenGateway

Thank you for considering contributing to OpenGateway. This project is MIT-licensed and all contributions are welcome.

## Getting Started

```bash
# Clone the repository
git clone https://github.com/echohello-dev/opengateway.git
cd opengateway

# Install Python dependencies
uv pip install -e ".[dev]"

# (Optional) Install pixi for the Mojo (flare) variant
curl -fsSL https://pixi.sh/install.sh | sh
pixi install -e mojo

# Run Python tests
pytest

# Run Mojo tests
pixi run -e mojo mojo run opengateway/mojo/test_router.mojo

# Lint everything
ruff check .
ruff format .
mypy opengateway/

# Start the FastAPI gateway
opengateway

# Start the Mojo (flare) gateway
pixi run -e mojo mojo run opengateway/mojo/main.mojo
```

## Code Style

- Python 3.11+ with type hints
- Mojo nightly + pixi for the Mojo (flare) variant
- Formatting with `ruff format` (Python) and `mojo format` (Mojo)
- Type checking with `mypy` (Python) — Mojo types are compiler-checked
- Maximum line length: 100 characters

## Architecture

OpenGateway ships **two HTTP servers** that implement the same OpenAI-compatible contract:

1. **Mojo + flare server** (`opengateway/mojo/main.mojo`), default, Mojo, static binary.
2. **FastAPI server** (`opengateway/main.py`), opt-in dev path, Python, asyncio.

Both delegate provider calls to the same Python adapters
(`opengateway/providers/`). The Mojo server uses the PythonObject
bridge (`opengateway/mojo_bridge/`) to call into Python for auth,
validation, and upstream dispatch.

When adding a new feature:

- **Provider adapters, DB access, observability** → Python (shared between both servers).
- **HTTP routes, middleware, response shapes** → both servers, kept thin and delegating.
- **Pure hot-path logic that benefits from Mojo** (token counting, routing scores) → Mojo, with the Python side as a fallback.

See [docs/architecture.md](docs/architecture.md) and
[ADR-002](adr/002-mojo-api-surface.md) for the full layering
rationale.

### Repository layout

```
opengateway/
├── opengateway/
│   ├── main.py              # FastAPI server (opt-in dev path)
│   ├── auth.py              # Virtual key + root key auth
│   ├── config.py            # Settings via pydantic-settings (RouteRule, ROUTES_JSON)
│   ├── keys.py              # API key generator (sk-og-{token})
│   ├── router.py            # Model-to-provider routing (Python)
│   ├── providers/           # Provider adapters (called by the bridge)
│   │   ├── base.py
│   │   ├── openai.py
│   │   └── anthropic.py     # stub, falls back from OpenAI when configured
│   ├── mojo/                # Mojo server on flare, default deployment
│   │   ├── main.mojo        # flare HTTP server + middleware stack
│   │   ├── router.mojo      # Model to provider module routing
│   │   ├── test_router.mojo
│   │   └── __init__.mojo
│   └── mojo_bridge/         # Python side of the Mojo bridge
│       ├── auth.py
│       ├── chat.py
│       ├── stream.py
│       ├── db.py            # Postgres virtual key store
│       ├── ratelimit.py     # Redis sliding-window rate limiter
│       └── routing.py       # ROUTES_JSON resolution + fallback orchestration
├── tests/                   # pytest suite + mock_upstream.py
├── docs/                    # architecture.md, configuration.md, release-process.md
├── adr/                     # Architecture Decision Records
├── pyproject.toml           # Python package config
├── pixi.toml                # Mojo environment config
├── Dockerfile               # Container build
└── docker-compose.yml       # Local dev stack (Postgres + Redis + gateway)
```

## Pull Request Process

1. Ensure your code passes all tests and linting (`ruff`, `mypy`,
   `pytest`, `mojo run opengateway/mojo/test_router.mojo`)
2. Update documentation if needed (`docs/`, `README.md`, `adr/`)
3. Open a pull request with a clear description
4. Use [Conventional Commits](https://www.conventionalcommits.org/)
   for commit messages — release-please uses them to drive versioning
   and changelogs. See [docs/release-process.md](docs/release-process.md).

## Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
`build`, `ci`, `chore`, `revert`. Breaking changes add a `!` after
the type/scope and a `BREAKING CHANGE:` footer.
