# Architecture

OpenGateway is an OpenAI-compatible LLM gateway. It exposes a single
`POST /v1/chat/completions` endpoint (plus `/health`) and dispatches
requests to upstream providers based on the requested model.

This document describes the runtime architecture, the dual-server
design (Python FastAPI + Mojo on flare), and the boundaries between
them.

## High-level request flow

```
                            ┌─────────────────────┐
   OpenAI-compatible client │  POST /v1/chat/...  │
   (curl, openai-python,    │  Bearer <virtual    │
    SDK, internal app) ────►│  key>               │
                            └─────────┬───────────┘
                                      │
                ┌─────────────────────┴─────────────────────┐
                │                                           │
        ┌───────▼────────┐                         ┌───────▼────────┐
        │  FastAPI app   │                         │  flare server  │
        │  (opengateway  │                         │  (opengateway  │
        │   .main)       │                         │   .mojo.main)  │
        │                │                         │                │
        │  Python,       │                         │  Mojo, static  │
        │  uvicorn,      │                         │  binary or     │
        │  asyncio       │                         │  pixi run      │
        └───────┬────────┘                         └───────┬────────┘
                │                                           │
                │      ┌────────────────────────────────┐   │
                └─────►│  opengateway.providers.*       │◄──┘
                       │  (Python adapters, async)       │
                       │  - openai.py  (existing)       │
                       │  - anthropic.py (planned)      │
                       │  - bedrock.py  (planned)       │
                       └────────────────┬───────────────┘
                                        │
                              ┌─────────▼──────────┐
                              │  Upstream LLM API  │
                              │  (OpenAI / Anthrop │
                              │   ic / Bedrock...) │
                              └────────────────────┘
```

Both servers implement the same endpoint contract, share the same
provider adapters, and share the same auth and config layers. A
deployment chooses one or the other at startup via the `GATEWAY_SERVER`
environment variable (default `fastapi`).

## Why two servers?

The two servers are not redundant — they optimise for different
constraints.

| Concern | FastAPI server | Mojo (flare) server |
|---|---|---|
| Language | Python | Mojo |
| Runtime | asyncio on uvicorn | sync handlers on thread-per-core reactor |
| Type system | Pydantic runtime validation | Compiled, monomorphised, with typed extractors |
| Build artifact | Source + interpreter + dependencies (~150 MB container) | Single static binary (~30 MB) |
| Ecosystem | Full Python ecosystem (httpx, asyncpg, redis, structlog) | Mojo stdlib + flare; Python libs reachable via PythonObject bridge |
| Maturity | Production-proven (700+ contributors) | Young (3 contributors, v0.8.0) |
| Cold start | ~1.5 s (interpreter startup) | <50 ms (static binary) |
| Throughput (local bench) | ~12 k req/s | ~240 k req/s (flare_mc_static) |
| Ideal use | Default server. Use everywhere unless you have a reason not to. | Edge / Lambda / serverless / managed SaaS Phase 3. |

For an open-source project, **the FastAPI server is the default**. The
Mojo server exists for two reasons:

1. **Positioning.** It is a concrete expression of the strategy note
   in `Notes/2026-05-01 - OpenGateway AI Gateway Research and Strategy.md`:
   "Bifrost is Go. OpenGateway is Python/Mojo - easier to customise."
   Shipping on Mojo is the differentiator.
2. **Operational shape.** A static binary is dramatically easier to
   ship, scan, and scale for the managed SaaS tier. One CVE stream,
   not `fastapi + pydantic + httpx + asyncpg + redis + structlog + ...`.

## Where the Mojo ↔ Python boundary lives

The Mojo layer is responsible for:
- HTTP parsing, routing, response serialisation
- Middleware composition (Logger, RequestId, Compress, CatchPanic, Cors)
- Connection management (TLS, keep-alive, graceful drain)
- Static binary deployment

The Python layer is responsible for:
- Auth (`opengateway.mojo_bridge.auth`)
- Request validation (`opengateway.mojo_bridge.chat`)
- Provider dispatch (`opengateway.mojo_bridge.chat._load_provider_class`)
- Provider calls (`opengateway.providers.*`)
- Settings, observability, anything else Python is better at

The boundary is a single synchronous function call from Mojo into
Python (`bridge_module.handle_chat(payload, auth_header, provider_module)`).
It returns an envelope dict `{"status": <int>, "body": <json str>}`
so the Mojo handler never has to catch Python exceptions itself.

```
Mojo handler                          Python bridge
─────────────                         ──────────────
chat_completions(req)                 handle_chat(body, auth, module)
  │                                     │
  │ req.text()                          │ authenticate_authorization()
  │ req.headers.get("authorization")    │ _validate_request(body)
  │                                     │ _enforce_model_access(...)
  │                                     │ _enforce_budget(...)
  │                                     │ asyncio.run(_run_completion(...))
  │                                     │   └─► provider.chat(...)
  │                                     │
  │ json_loads(body_text)               │
  │ bridge.handle_chat(payload, ...)    │
  │                                     │
  │ ◄──────────── envelope dict ────────│
  │
  ▼
ok_json(body_json)
```

The Mojo layer never calls `httpx`, `asyncpg`, or any async Python
library directly. Every async provider call goes through
`asyncio.run` inside the bridge, which is acceptable because the
Mojo layer does not own an event loop — each request gets its own
short-lived loop on the bridge thread.

## Adding a provider

To add a new provider (Anthropic, Bedrock, Mistral, etc.):

1. Add the API key to `Settings` in `opengateway/config.py`.
2. Implement `BaseProvider` in `opengateway/providers/<name>.py`.
3. Add a routing rule in `opengateway/mojo/router.mojo` **and** in
   the Python mirror at the bottom of `tests/test_mojo_bridge.py`.
4. Add an entry to the README provider matrix.

The Python bridge dynamically imports the provider module by string
name, so the Mojo layer never needs to know provider-specific code.

## Adding a route

For both servers:

- FastAPI: add a `@app.<method>` decorator in `opengateway/main.py`.
- Mojo: add `router.<method>(path, handler)` in
  `opengateway/mojo/main.mojo`.

Keep the two handlers thin and delegate the actual logic to
`opengateway.mojo_bridge`. That keeps the route definitions short
and the logic in one place (Python), avoiding drift between the
two servers.

## Deployment shapes

```
┌────────────────────────────┐
│ Local dev (Python default) │
│                            │
│   uv run opengateway       │
│   (uses opengateway.main   │
│    FastAPI app on :8080)   │
└────────────────────────────┘

┌────────────────────────────┐
│ Edge / serverless          │
│                            │
│   pixi run -e mojo mojo    │
│     build main.mojo -O3    │
│   ./main                   │
│   (static binary, no venv, │
│    15–80 MB)               │
└────────────────────────────┘

┌────────────────────────────┐
│ Docker (default)           │
│                            │
│   docker compose up        │
│   (FastAPI + Postgres +    │
│    Redis via Compose)      │
└────────────────────────────┘

┌────────────────────────────┐
│ Docker (Mojo variant)      │
│                            │
│   pixi run -e mojo mojo    │
│     build main.mojo        │
│   docker build -f          │
│     Dockerfile.mojo .      │
│   (multi-stage:           │
│    modular image → static  │
│    binary → distroless     │
│    final image, ~30 MB)    │
└────────────────────────────┘
```

See `docs/release-process.md` for the full release flow and
`docs/mojo-python-ai-gateway.md` for the design rationale.
