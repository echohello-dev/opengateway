<div align="center">

<img src="docs/assets/banner.gif" alt="OpenGateway, the AI gateway that doesn't paywall the features" width="100%">

**The fastest way to add SSO, audit logs, guardrails, and routing to any AI app.**

OpenAI-compatible. Every feature free. MIT, forever.

[Docs](docs/architecture.md) · [Quick Start](#quick-start) · [Drop-in Replacement](#drop-in-replacement) · [Providers](#providers) · [Configuration](docs/configuration.md) · [ADRs](adr/)

|         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CI/CD   | [![CI](https://github.com/echohello-dev/opengateway/actions/workflows/ci.yml/badge.svg)](https://github.com/echohello-dev/opengateway/actions) [![release-please](https://github.com/echohello-dev/opengateway/actions/workflows/release-please.yml/badge.svg)](https://github.com/echohello-dev/opengateway/actions) |
| Docs    | [![Website](https://img.shields.io/website?label=documentation&up_message=online&url=https%3A//docs.opengateway.dev)](https://docs.opengateway.dev) |
| Package | [![License: MIT](https://img.shields.io/github/license/echohello-dev/opengateway?color=blue)](LICENSE) |
| Meta    | [![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org) [![Mojo](https://img.shields.io/badge/mojo-🔥-f44a03)](https://www.modular.com/mojo) [![Stars](https://img.shields.io/github/stars/echohello-dev/opengateway)](https://github.com/echohello-dev/opengateway/stargazers) |

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

> "Bifrost is Go. OpenGateway is Python/Mojo, easier to customise."

And unlike every other Python AI gateway, OpenGateway ships a **second server on Mojo + [flare](https://github.com/ehsanmok/flare)**: one static binary for the edge.

---

## Quick Start

### Default: Mojo (flare), single static binary

```bash
$ curl -fsSL https://pixi.sh/install.sh | sh     # one-time
$ pixi install -e mojo
$ pixi run -e mojo mojo run opengateway/mojo/main.mojo
opengateway (mojo): listening on 0.0.0.0:8080 with 4 workers
```

Or build a ~30 MB distroless container image:

```bash
$ docker build -t opengateway:mojo .
$ docker run --rm -p 8080:8080 --env-file .env opengateway:mojo
```

### Python (FastAPI, opt-in for local dev)

```bash
$ uv pip install -e ".[dev]"
$ cp .env.example .env && $EDITOR .env   # set ROOT_KEY and OPENAI_API_KEY
$ opengateway
INFO:     Uvicorn running on http://0.0.0.0:8080
```

Both servers implement the same `POST /v1/chat/completions` endpoint and share the same provider adapters. Production ships the Mojo binary; FastAPI stays in-tree as the Python-only dev path. See [docs/architecture.md](docs/architecture.md) for the full story.

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

No API key? Run the bundled mock upstream and exercise the full path offline ([docs/configuration.md](docs/configuration.md)).

---

## Drop-in Replacement

Point any OpenAI-compatible client at OpenGateway with one line. Same API, same SDK, no code changes.

```diff
# Python (openai SDK)
- client = OpenAI(api_key="sk-...")
+ client = OpenAI(base_url="http://localhost:8080/v1", api_key="sk-og-...")

# TypeScript (openai SDK)
- const client = new OpenAI({ apiKey: "sk-..." })
+ const client = new OpenAI({ baseURL: "http://localhost:8080/v1", apiKey: "sk-og-..." })

# curl
- curl https://api.openai.com/v1/chat/completions ...
+ curl http://localhost:8080/v1/chat/completions ...
```

Every OpenAI SDK works without modification. Anthropic, Google GenAI, LiteLLM, and LangChain SDKs work the same way through the provider router.

---

## Features

### Core Infrastructure

- **OpenAI-compatible endpoint.** Same request shape, same response shape, same error format.
- **Multi-provider support.** OpenAI, Anthropic, AWS Bedrock, Google Vertex, Azure, and more, behind a single API.
- **Automatic fallbacks.** Seamless failover between providers and models with zero downtime.
- **Streaming (SSE).** Server-sent events out of the box, same wire format as OpenAI.

### Governance and Security

- **Virtual keys with model allow-lists.** Per-key permissions restrict which models each caller can hit.
- **Per-key budgets and rate limits.** Token-bucket rate limiting and USD budget caps per virtual key.
- **Audit logs.** Structured events for every request, queryable by key, model, and time range.
- **SSO / SAML.** OIDC and SAML authentication for admin interfaces and key management.
- **RBAC, IP ACLs, custom branding.** Team hierarchies, source-IP restrictions, per-tenant theming.

### Observability and Developer Experience

- **Native Prometheus metrics.** Request counts, latency histograms, error rates, token usage.
- **Structured request logging.** JSON logs with key, model, latency, tokens, and cost.
- **Zero-config startup.** Single command, single binary, no database required to start.
- **Standard formats everywhere.** OpenAPI for the spec, JSON for config, dotenv for env.

---

## Providers

| Provider | Status | Routing prefixes | Key env var |
|---|---|---|---|
| **OpenAI** | shipped | `gpt-*`, `openai/*` | `OPENAI_API_KEY` |
| **Anthropic** | routed, adapter pending | `claude-*`, `anthropic/*` | `ANTHROPIC_API_KEY` |
| **AWS Bedrock** | routed, adapter pending | `bedrock/*`, `amazon.*` | _(AWS credentials)_ |
| **Azure OpenAI** | planned | `azure/*` | `AZURE_OPENAI_API_KEY` |
| **Google Vertex** | planned | `vertex/*` | _(GCP credentials)_ |
| **vLLM / local** | planned | `local/*` | _(none)_ |

[Adding a provider](docs/architecture.md#adding-a-provider) takes three steps: implement `BaseProvider`, add a routing rule, configure the key.

---

## Architecture

```mermaid
flowchart TD
    client["OpenAI-compatible client"] --> api["HTTP API surface<br/>flare on Mojo, default<br/>or FastAPI, Python, opt-in"]
    api --> bridge["PythonObject bridge<br/>only in the Mojo path"]
    bridge -->|"single sync function call<br/>returns envelope dict"| logic["Python business logic<br/>auth, validation, provider dispatch"]
    logic --> adapters["Provider adapters<br/>opengateway/providers/{openai,anthropic,bedrock,...}.py"]
    adapters --> upstream["Upstream LLM API<br/>OpenAI / Anthropic / Bedrock / ..."]
```

**Mojo on flare** is the default. Single static binary, sub-50 ms cold start, ~30 MB image, no `pip install` in your container. It hosts the entire HTTP surface natively: routing, middleware, SSE, request-id propagation, structured logging, panic safety, graceful drain. **FastAPI** stays in-tree as the Python-only dev path for local iteration on the bridge or when you need a debugger attached to the Python stack.

Both servers share the same provider adapters, the same auth, the same config. The Mojo to PythonObject boundary is one synchronous function call (`bridge.handle_chat`) that returns an envelope dict so the Mojo handler never catches Python exceptions.

Full layout in [docs/architecture.md](docs/architecture.md); the decision to make Mojo the default lives in [ADR-003](adr/003-mojo-default.md); the original dual-server rationale is in [ADR-002](adr/002-mojo-api-surface.md).

---

## Philosophy

A few principles we hold ourselves to. They're non-negotiable.

1. **Every feature ships in the OSS build.** SSO, audit logs, guardrails, advanced routing. None of them are paywalled. The code is the product.
2. **OpenAI-compatible is the API contract.** Not "compatible-ish". Not "subset". The same request shape, the same response shape, the same error format.
3. **Boring tech where it matters.** FastAPI, Postgres, Redis, Pydantic. We don't get bonus points for picking weird.
4. **New tech where it pays off.** Mojo for the binary-deploy path. Conventional commits for release automation. Standard formats everywhere else.
5. **Tests in CI, not in promises.** No `// TODO: test this later` in main.
6. **The README is a contract.** If it doesn't run as written, the docs are wrong, not the code.

---

## Documentation

| Doc | What it covers |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Runtime layout, dual-server design, Mojo to Python boundary |
| [docs/configuration.md](docs/configuration.md) | Env vars, routing table, cost caps, fallbacks, TLS, mock upstream |
| [docs/release-process.md](docs/release-process.md) | release-please flow, conventional commits, PyPI trusted publisher |
| [docs/mojo-python-ai-gateway.md](docs/mojo-python-ai-gateway.md) | Original design sketch (historical rationale) |
| [docs/assets/logo-explore](docs/assets/logo-explore/) | Brand assets: mark and lockup SVGs, banner source, logo animation |
| [adr/001-api-key-format.md](adr/001-api-key-format.md) | The `sk-og-{token}` key format |
| [adr/002-mojo-api-surface.md](adr/002-mojo-api-surface.md) | Why Mojo for the API surface |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, commit conventions, PR process |

---

## Contributing

We accept contributions under [DCO](./CONTRIBUTING.md). Commits follow [Conventional Commits](https://www.conventionalcommits.org/). `release-please` uses your commit messages to drive the version bump and the changelog, so prefix your commits with `feat:`, `fix:`, `docs:`, etc.

```bash
make test           # pytest
make lint           # ruff + mypy
make mojo-test      # Mojo router tests (requires pixi)
```

---

## Project Status

OpenGateway is alpha (0.x). The core proxy works end-to-end with the OpenAI provider; Anthropic and Bedrock adapters are routed but not yet implemented, and expect breaking changes before 1.0. Watch [releases](https://github.com/echohello-dev/opengateway/releases) for tagged versions, and check the [open issues](https://github.com/echohello-dev/opengateway/issues) for the current picture.

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
