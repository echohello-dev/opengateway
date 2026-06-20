# OpenGateway

An open-source AI gateway. All features free — SSO, audit logs, guardrails, advanced routing. Monetised through managed hosting and support.

## Quick Start

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run the gateway (FastAPI, default)
opengateway

# Or with uvicorn directly
uvicorn opengateway.main:app --reload --port 8080

# Run the Mojo (flare) variant — requires pixi + modular
pixi install -e mojo
pixi run -e mojo mojo run opengateway/mojo/main.mojo
```

## Architecture

OpenGateway ships **two servers** that implement the same OpenAI-compatible contract:

| Server | Language | Runtime | When to use |
|---|---|---|---|
| **FastAPI** (default) | Python | asyncio on uvicorn | Local dev, default deployments, anywhere Python runs. |
| **Mojo + flare** | Mojo | sync handlers on thread-per-core reactor | Edge / Lambda / serverless / Phase 3 SaaS hosting. Static binary, ~30 MB. |

Both share the same provider adapters (`opengateway/providers/`), auth (`opengateway/auth.py`), and config (`opengateway/config.py`). The Mojo server delegates all business logic to the Python bridge (`opengateway/mojo_bridge/`) via `PythonObject`. See [docs/architecture.md](docs/architecture.md) and [ADR-002](adr/002-mojo-api-surface.md).

## Configuration

Set via environment variables or create a `.env` file:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost/opengateway
REDIS_URL=redis://localhost:6379/0
ROOT_KEY=sk-root-change-me

# Provider keys
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
```

## Endpoints

```
GET  /health                  → 200 {"status": "ok"}
POST /v1/chat/completions     → OpenAI-compatible chat completion
```

## Testing

```bash
# Python
uv run pytest -v

# Mojo (router unit tests)
pixi run -e mojo mojo run opengateway/mojo/test_router.mojo
```

## Documentation

- [docs/architecture.md](docs/architecture.md) — runtime layout, dual-server design, where the Mojo ↔ Python boundary lives
- [docs/release-process.md](docs/release-process.md) — release-please flow, conventional commits, PyPI publishing
- [docs/mojo-python-ai-gateway.md](docs/mojo-python-ai-gateway.md) — original design sketch
- [adr/001-api-key-format.md](adr/001-api-key-format.md) — `sk-og-{token}` format
- [adr/002-mojo-api-surface.md](adr/002-mojo-api-surface.md) — why Mojo for the API surface

## License

MIT — see [LICENSE](LICENSE)
