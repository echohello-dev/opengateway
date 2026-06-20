# OpenGateway

An open-source AI gateway. All features free — SSO, audit logs, guardrails, advanced routing. Monetised through managed hosting and support.

## Quick Start

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run the gateway
opengateway

# Or with uvicorn directly
uvicorn opengateway.main:app --reload --port 8080
```

## Configuration

Set via environment variables or create a `.env` file:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost/opengateway
REDIS_URL=redis://localhost:6379/0
ROOT_KEY=sk-root-change-me
```

## License

MIT — see [LICENSE](LICENSE)
