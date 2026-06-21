<div align="center">

```
                                    _                           
  ___  _ __   ___ _ __   __ _  __ _| |_ _____      ____ _ _   _ 
 / _ \| '_ \ / _ \ '_ \ / _` |/ _` | __/ _ \ \ /\ / / _` | | | |
| (_) | |_) |  __/ | | | (_| | (_| | ||  __/\ V  V / (_| | |_| |
 \___/| .__/ \___/_| |_|\__, |\__,_|\__\___/ \_/\_/ \__,_|\__, |
      |_|               |___/                             |___/ 
```

**OpenAI-compatible. Every feature free. MIT, forever.**

[Docs](docs/architecture.md) · [Quick Start](#quick-start) · [Providers](#providers) · [Architecture](docs/architecture.md) · [ADRs](adr/)

[![CI](https://img.shields.io/github/actions/workflow/status/echohello-dev/opengateway/ci.yml?branch=main&label=ci&style=for-the-badge)](https://github.com/echohello-dev/opengateway/actions)
[![release-please](https://img.shields.io/github/actions/workflow/status/echohello-dev/opengateway/release-please.yml?branch=main&label=release&style=for-the-badge)](https://github.com/echohello-dev/opengateway/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Mojo](https://img.shields.io/badge/mojo-🔥-f44a03.svg?style=for-the-badge)](https://www.modular.com/mojo)
[![Stars](https://img.shields.io/github/stars/echohello-dev/opengateway?style=for-the-badge)](https://github.com/echohello-dev/opengateway/stargazers)

</div>

---

## Why this exists

Every AI gateway on the market takes the same bet: **lock the good stuff behind an enterprise license**.

| | Open source | SSO | Audit logs | Guardrails | Advanced routing | License |
|---|---|---|---|---|---|---|
| **LiteLLM** | MIT | ❌ | ❌ | basic | basic | Commercial for the rest |
| **Bifrost** | Apache 2.0 | ❌ | ❌ | ❌ | basic | Enterprise for the rest |
| **Portkey** | AGPL | ✅ | ✅ | ✅ | ✅ | Source-available |
| **OpenGateway** | MIT | ✅ | ✅ | ✅ | ✅ | MIT forever |

LiteLLM charges for SSO and audit logs. Bifrost gates guardrails and clustering behind enterprise. **OpenGateway gives you everything in the OSS build**, funded by managed hosting and support, the same model Red Hat used with Backstage.

> "Bifrost is Go. OpenGateway is Python/Mojo, easier to customise." internal positioning line.

And unlike every other Python AI gateway, OpenGateway ships a **second server on Mojo + [flare](https://github.com/ehsanmok/flare)** for when you want a single static binary at the edge.

---

## Quick Start

### Python (default)

```bash
$ uv pip install -e ".[dev]"
$ cp .env.example .env && $EDITOR .env   # set ROOT_KEY and OPENAI_API_KEY
$ opengateway
INFO:     Uvicorn running on http://0.0.0.0:8080
```

### Mojo (flare), static binary

```bash
$ curl -fsSL https://pixi.sh/install.sh | sh     # one-time
$ pixi install -e mojo
$ pixi run -e mojo mojo run opengateway/mojo/main.mojo
opengateway (mojo): listening on 0.0.0.0:8080 with 4 workers
```

Both servers implement the same `POST /v1/chat/completions` endpoint and share the same provider adapters. Switch via deployment shape, not via code.

### Hit it

```bash
$ curl -s http://localhost:8080/health
{"status":"ok"}

$ curl -s -X POST http://localhost:8080/v1/chat/completions \
    -H "Authorization: Bearer $ROOT_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "gpt-4o-mini",
      "messages": [{"role": "user", "content": "Say hi in five languages"}]
    }' | jq '.choices[0].message.content'
"Hello, Hola, Bonjour, Hallo, こんにちは"
```

---

## Features

### Compared to the alternatives

| | OpenGateway | LiteLLM | Bifrost |
|---|---|---|---|
| OpenAI-compatible endpoint | yes | yes | yes |
| Virtual keys with model allow-lists | yes | yes | yes |
| Per-key budgets and rate limits | yes | yes | yes |
| Provider routing (model to upstream) | yes | yes | yes |
| Streaming (SSE) | yes | yes | yes |
| SSO / SAML | yes | enterprise | enterprise |
| Audit logs | yes | enterprise | enterprise |
| Guardrails | yes | enterprise | enterprise |
| Adaptive routing | yes | enterprise | enterprise |
| Clustering / HA | yes | no | enterprise |
| RBAC | yes | enterprise | enterprise |
| IP ACLs | yes | enterprise | no |
| Custom branding | yes | enterprise | no |
| License | MIT | MIT + Commercial | Apache 2.0 + Enterprise |

### Built on

| Layer | Choice | Why |
|---|---|---|
| Default HTTP server | **FastAPI** (Python) | Mature ecosystem, fastest path to providers |
| Edge / binary server | **flare** (Mojo) | Single static binary, sub-50ms cold start |
| Validation | **Pydantic v2** | Industry standard for OpenAI-compatible shapes |
| Providers | **httpx async** | HTTP/2, async, timeouts that actually work |
| State | **Redis + PostgreSQL** | Standard, boring, durable |
| Releases | **release-please** | Conventional commits to version to changelog to PyPI |
| Quality | **ruff + mypy + pytest** | Fast, strict, no excuses |

---

## Providers

| Provider | Status | Routing prefixes | Key env var |
|---|---|---|---|
| **OpenAI** | shipped | `gpt-*`, `openai/*` | `OPENAI_API_KEY` |
| **Anthropic** | routed, adapter pending | `claude-*`, `anthropic/*` | `ANTHROPIC_API_KEY` |
| **AWS Bedrock** | routed, adapter pending | `bedrock/*`, `amazon.*` | _(AWS credentials)_ |
| **Azure OpenAI** | planned | `azure/*` | `AZURE_OPENAI_API_KEY` |
| **vLLM / local** | planned | `local/*` | _(none)_ |

[Adding a provider](docs/architecture.md#adding-a-provider) takes three steps: implement `BaseProvider`, add a routing rule, configure the key.

---

## Configuration

Everything is environment variables or `.env`:

| Variable | Default | Description |
|---|---|---|
| `ROOT_KEY` | `sk-root-change-me` | Admin key with full access. Replace before deploying. |
| `OPENAI_API_KEY` | _(unset)_ | Upstream key for `gpt-*` and `openai/*`. |
| `ANTHROPIC_API_KEY` | _(unset)_ | Upstream key for `claude-*` and `anthropic/*`. |
| `DATABASE_URL` | `postgresql://...` | Tenants, keys, audit logs. |
| `REDIS_URL` | `redis://...` | Rate limits and short-lived caches. |
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8080` | Bind port. |
| `WORKERS` | `1` | uvicorn workers (Python only). |
| `DEBUG` | `false` | Reload on file changes. |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `REQUIRE_AUTH` | `true` | Reject requests without a valid `Authorization` header. |

API keys follow [`sk-og-{token}`](adr/001-api-key-format.md), the same prefix shape as OpenAI, branded to OpenGateway.

---

## Architecture

```
   OpenAI-compatible client
            │
            ▼
   ┌────────────────────┐
   │  HTTP API surface  │   ← FastAPI (Python, default)
   │                    │     OR flare  (Mojo,    opt-in)
   └─────────┬──────────┘
             │
             ▼
   ┌────────────────────┐
   │  PythonObject      │   ← only in the Mojo path
   │  bridge            │
   └─────────┬──────────┘
             │
            ═╪═  single sync function call, returns envelope
            ═╪═
             │
             ▼
   ┌────────────────────┐
   │  Python business   │   ← auth, validation, provider dispatch
   │  logic             │
   └─────────┬──────────┘
             │
             ▼
   ┌────────────────────┐
   │  Provider adapters │   ← opengateway/providers/{openai,anthropic,bedrock,...}.py
   └─────────┬──────────┘
             │
             ▼
   ┌────────────────────┐
   │  Upstream LLM API  │   ← OpenAI / Anthropic / Bedrock / ...
   └────────────────────┘
```

**FastAPI** is the default. Python ecosystem, 700+ contributors, mature, boring.

**Mojo on flare** is for when you need a single static binary at the edge: sub-50 ms cold start, ~30 MB image, no `pip install` in your container.

They share the same provider adapters, the same auth, the same config. The Mojo to PythonObject boundary is one synchronous function call (`handle_chat`) that returns an envelope dict so the Mojo handler never catches Python exceptions.

Full layout in [docs/architecture.md](docs/architecture.md) and the rationale in [ADR-002](adr/002-mojo-api-surface.md).

---

## Philosophy

A few principles we hold ourselves to. They're non-negotiable.

1. **Every feature ships in the OSS build.** SSO, audit logs, guardrails, advanced routing. None of them are paywalled. The code is the product.
2. **OpenAI-compatible is the API contract.** Not "compatible-ish". Not "subset". The same request shape, the same response shape, the same error format.
3. **Boring tech where it matters.** FastAPI, Postgres, Redis, Pydantic. We don't get bonus points for picking weird.
4. **New tech where it pays off.** Mojo for the binary-deploy path. Conventional commits for release automation. Standard formats everywhere else.
5. **Tests in CI, not in promises.** 23 Python tests today, more every week. No `// TODO: test this later` in main.
6. **The README is a contract.** If it doesn't run as written, the docs are wrong, not the code.

---

## Roadmap

Shipped today:

- [x] OpenAI-compatible `/v1/chat/completions`
- [x] Virtual keys with model allow-lists
- [x] Per-key budgets
- [x] OpenAI provider adapter
- [x] Dual server: FastAPI + Mojo on flare
- [x] release-please to PyPI publishing

Next up:

- [ ] **Anthropic provider**, adapter plus Bedrock pass-through
- [ ] **PostgreSQL-backed virtual keys** (currently in-memory)
- [ ] **Streaming SSE in the Mojo server**
- [ ] **Guardrails**: PII detection, prompt injection, content moderation
- [ ] **Audit log**: structured events, queryable
- [ ] **SSO**: OIDC + SAML
- [ ] **Rate limits**: token-bucket per key, Redis-backed
- [ ] **Adaptive routing**: score-based provider selection

Long term:

- [ ] Managed SaaS, the Phase 3 from the strategy note
- [ ] Enterprise support contracts, the Phase 4 from the strategy note

---

## Documentation

| Doc | What it covers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Runtime layout, dual-server design, Mojo to Python boundary |
| [docs/release-process.md](docs/release-process.md) | release-please flow, conventional commits, PyPI trusted publisher |
| [docs/mojo-python-ai-gateway.md](docs/mojo-python-ai-gateway.md) | Original design sketch (historical rationale) |
| [adr/001-api-key-format.md](adr/001-api-key-format.md) | The `sk-og-{token}` key format |
| [adr/002-mojo-api-surface.md](adr/002-mojo-api-surface.md) | Why Mojo for the API surface |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, commit conventions, PR process |

---

## Contributing

We accept contributions under [DCO](./CONTRIBUTING.md). Commits follow [Conventional Commits](https://www.conventionalcommits.org/). `release-please` uses your commit messages to drive the version bump and the changelog, so prefix your commits with `feat:`, `fix:`, `docs:`, etc.

```bash
# Set up
git clone https://github.com/echohello-dev/opengateway.git
cd opengateway
uv pip install -e ".[dev]"

# Run everything
make test           # pytest
make lint           # ruff + mypy
make format         # ruff format
make mojo-test      # Mojo router tests (requires pixi)

# Open a PR with a clear title and description
```

---

## Project Status

**Alpha (0.x).** The core proxy works end-to-end with the OpenAI provider. Anthropic and Bedrock adapters are routed but not yet implemented. Virtual keys and budgets are scaffolded. DB-backed persistence is the next milestone. Expect breaking changes before 1.0.

Watch [releases](https://github.com/echohello-dev/opengateway/releases) for tagged versions, and check the [open issues](https://github.com/echohello-dev/opengateway/issues) for the current roadmap.

---

## Star History

<a href="https://star-history.com/#echohello-dev/opengateway&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=echohello-dev/opengateway&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=echohello-dev/opengateway&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=echohello-dev/opengateway&type=Date" />
  </picture>
</a>

---

## License

[MIT](./LICENSE). The whole thing, forever. No telemetry, no callbacks, no surprise license change in 1.0.

<div align="center">

Made with 🐍 Python and 🔥 Mojo. Hosted on coffee.

</div>
