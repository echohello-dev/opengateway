# OpenGateway

**An open-source AI gateway — OpenAI-compatible, every feature free, monetised through managed hosting.**

OpenGateway sits between your code and upstream LLM providers (OpenAI, Anthropic, Bedrock, …).
It gives you one stable `POST /v1/chat/completions` endpoint, swaps providers transparently,
enforces budgets and per-key model access, and ships every feature — SSO, audit logs,
guardrails, advanced routing — without an enterprise paywall.

LiteLLM charges for SSO and audit logs. Bifrost gates guardrails behind enterprise. OpenGateway
is MIT, forever, and [the code is the product](./docs/architecture.md).

---

## Highlights

- **OpenAI-compatible.** Drop in any OpenAI client SDK; point it at OpenGateway.
- **Two servers, one contract.** FastAPI (Python, default) and Mojo on
  [flare](https://github.com/ehsanmok/flare) (static binary, opt-in).
- **Provider-agnostic routing.** Prefix-based model routing — `gpt-*` → OpenAI,
  `claude-*` → Anthropic, `bedrock/*` → AWS Bedrock.
- **Per-key budgets and model allow-lists.** Virtual keys with model restrictions and spend
  caps out of the box.
- **MIT licensed.** All features, no enterprise tier, no telemetry.

---

## Quick Start

### Python (default)

```bash
# Install
uv pip install -e ".[dev]"

# Configure
cp .env.example .env
# edit .env: set ROOT_KEY=sk-og-... and OPENAI_API_KEY=sk-...

# Run
opengateway

# In another shell:
curl http://localhost:8080/health
# {"status":"ok"}

curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $ROOT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Mojo (flare) — static binary

```bash
# Install pixi (one-time)
curl -fsSL https://pixi.sh/install.sh | sh

# Install the mojo environment + flare
pixi install -e mojo

# Run
pixi run -e mojo mojo run opengateway/mojo/main.mojo

# Or build a single static binary for production
pixi run -e mojo mojo build opengateway/mojo/main.mojo \
  -O3 -D ASSERT=none -o dist-mojo/opengateway-mojo
./dist-mojo/opengateway-mojo
```

The Mojo server delegates all business logic to the Python bridge, so both servers
share the same provider adapters, auth, and config. See
[docs/architecture.md](docs/architecture.md) for the full boundary diagram.

---

## Configuration

All config flows through environment variables or a `.env` file. The full list:

| Variable | Default | Description |
|---|---|---|
| `ROOT_KEY` | `sk-root-change-me` | Admin key with full access. Replace before deploying. |
| `OPENAI_API_KEY` | _(unset)_ | API key for `gpt-*` and `openai/*` models. |
| `ANTHROPIC_API_KEY` | _(unset)_ | API key for `claude-*` and `anthropic/*` models. |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/opengateway` | Postgres URL for tenants, keys, and audit logs. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL for rate-limit state and short-lived caches. |
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8080` | Bind port. |
| `WORKERS` | `1` | Number of uvicorn workers (Python server only). |
| `DEBUG` | `false` | Reload on file changes when `true`. |
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `REQUIRE_AUTH` | `true` | Reject requests without a valid Authorization header. |

API keys follow the [`sk-og-{32 chars}` format](adr/001-api-key-format.md) — same
prefix as OpenAI, branded to OpenGateway. ~190 bits of entropy.

---

## Endpoints

```
GET  /health                  → 200 {"status": "ok"}
POST /v1/chat/completions     → OpenAI-compatible chat completion
```

`POST /v1/chat/completions` accepts the standard OpenAI request body
(`model`, `messages`, `temperature`, `max_tokens`, `top_p`, `stream`, …) and
returns the standard OpenAI response shape. Any additional OpenAI fields
(`tools`, `response_format`, `logit_bias`, …) are passed through to the
upstream provider unchanged.

Streaming (`"stream": true`) is supported by the Python server. The Mojo server
currently returns non-streaming JSON only; full SSE support is tracked in the
follow-up roadmap.

---

## Provider Support

| Provider | Status | Routing prefixes | Key env var |
|---|---|---|---|
| OpenAI | ✅ Shipped | `gpt-*`, `openai/*` | `OPENAI_API_KEY` |
| Anthropic | 🚧 Routed, adapter pending | `claude-*`, `anthropic/*` | `ANTHROPIC_API_KEY` |
| AWS Bedrock | 🚧 Routed, adapter pending | `bedrock/*`, `amazon.*` | _(AWS credentials)_ |

Adding a new provider is three steps (full guide in
[docs/architecture.md](docs/architecture.md#adding-a-provider)):

1. Implement `BaseProvider` in `opengateway/providers/<name>.py`.
2. Add a routing rule in `opengateway/mojo/router.mojo`.
3. Add the API key to `Settings` in `opengateway/config.py`.

---

## Architecture in 30 Seconds

```
   OpenAI-compatible client
            │
            ▼
   ┌────────────────────┐
   │  HTTP API surface  │   ← FastAPI (Python, default) OR flare (Mojo, opt-in)
   └─────────┬──────────┘
             │
             ▼
   ┌────────────────────┐
   │  PythonObject      │   ← only present in the Mojo server
   │  bridge            │
   └─────────┬──────────┘
             │
             ▼
   ┌────────────────────┐
   │  Python business   │   ← auth, validation, provider dispatch
   │  logic             │
   └─────────┬──────────┘
             │
             ▼
   ┌────────────────────┐
   │  Provider adapters │   ← opengateway/providers/{openai,anthropic,bedrock}.py
   └─────────┬──────────┘
             │
             ▼
   ┌────────────────────┐
   │  Upstream LLM API  │   ← OpenAI / Anthropic / Bedrock / ...
   └────────────────────┘
```

The two servers are not redundant — they optimise for different deployment shapes.
**FastAPI is the default** (Python, ecosystem, maturity). **Mojo on flare** is for
edge, Lambda, and serverless where a single static binary and sub-50 ms cold
starts matter. Both implement the same OpenAI-compatible contract and share the
same provider adapters.

See [docs/architecture.md](docs/architecture.md) and
[ADR-002](adr/002-mojo-api-surface.md) for the full rationale.

---

## Documentation

- [docs/architecture.md](docs/architecture.md) — runtime layout, dual-server design, where the Mojo ↔ Python boundary lives
- [docs/release-process.md](docs/release-process.md) — release-please flow, conventional commits, PyPI publishing
- [docs/mojo-python-ai-gateway.md](docs/mojo-python-ai-gateway.md) — original design sketch (historical)
- [adr/001-api-key-format.md](adr/001-api-key-format.md) — `sk-og-{token}` key format
- [adr/002-mojo-api-surface.md](adr/002-mojo-api-surface.md) — why Mojo for the API surface

---

## Project Status

**Alpha (0.x).** The core proxy works end-to-end with the OpenAI provider.
Anthropic and Bedrock adapters are routed but not yet implemented. Virtual keys,
audit logs, and per-key budgets are scaffolded; DB-backed persistence is the next
milestone. Expect breaking changes before 1.0.

See the open issues for the current roadmap, or read
[docs/architecture.md](docs/architecture.md) for the long view.

---

## Contributing

Contributions are welcome under [DCO](./CONTRIBUTING.md). The repo uses
[Conventional Commits](https://www.conventionalcommits.org/) — release-please uses
your commit messages to drive versioning and the changelog, so prefix your commits
with `feat:`, `fix:`, `docs:`, etc.

```bash
# Set up
git clone https://github.com/echohello-dev/opengateway.git
cd opengateway
uv pip install -e ".[dev]"

# Run Python tests
pytest

# Run linting
ruff check .
ruff format .
mypy opengateway/

# Run the Mojo tests (requires pixi)
pixi install -e mojo
pixi run -e mojo mojo run opengateway/mojo/test_router.mojo
```

Full guide in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

[MIT](./LICENSE) — see the file for the full text.
