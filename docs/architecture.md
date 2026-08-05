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
deployment chooses one or the other at startup: production ships the
Mojo static binary as the image entrypoint (`Dockerfile`), while
`uv run opengateway` brings up the FastAPI dev server for working on the
bridge or a provider adapter.

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

For an open-source project, **the Mojo server is the default** as of
ADR-003 (2026-07-31). FastAPI stays in-tree as the Python-only dev path.
The Mojo server is the default because:

1. **Static binary deployment.** A single ~30 MB distroless image, no
   `pip install` in the container, sub-50 ms cold start.
2. **Single CVE stream.** One binary to patch instead of
   `fastapi + pydantic + httpx + asyncpg + redis + structlog + uvicorn + ...`.
3. **Mature middleware stack.** `CatchPanic`, `RequestId`, `StructuredLogger`,
   `Compress`, `Metrics`, `RateLimit`, `CircuitBreaker`, graceful drain —
   all in-box from flare v0.9, no third-party middleware required.
4. **Typed extractors + typed streaming-proxy surface.** `PathInt`, `Json[T]`,
   `HeaderStr`, `StreamHandler`, `UpstreamChunkSource` — compile-time
   guarantees on request shape and a designed-for shape for an LLM
   gateway's streaming path.

The FastAPI server stays as the Python-only dev path (`uv run opengateway`)
for local iteration on the bridge or a provider adapter. The boundary
with Python is unchanged: provider SDKs, auth, settings, anything
stateful all stay in the bridge.

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

### Streaming

For `stream: true` the bridge validates synchronously (so 4xx/5xx
fail before SSE headers are written), then spawns a pump thread per
request that drives `provider.chat_stream` and pushes OpenAI-shaped
SSE frames into a bounded `queue.Queue` (maxsize 64). The Mojo
handler wraps the returned `StreamHandle` in a `ChunkSource`
(`PythonQueueSource` in `opengateway/mojo/main.mojo`) and serves it
via flare's `stream_response`, which frames each chunk as HTTP/1.1
chunked transfer-encoding (or h2 DATA frames) with the canonical SSE
headers. The queue's bound couples upstream reads to downstream drain;
client disconnect flips the request `Cancel` token, the source calls
`handle.cancel()`, and the pump unwinds between frames.

The trade-off: `PythonQueueSource.next` blocks the flare worker up to
500 ms per pull, so a worker serves one streaming request at a time —
the same blocking profile as the non-streaming path. Size
`num_workers` for concurrent streaming load. The flare-native upgrade
(`serve_streaming` + `UpstreamChunkSource` over a UDS) removes the
blocking pull and is tracked as a follow-up in ADR-003.

## Adding a provider

To add a new provider (Anthropic, Bedrock, Mistral, etc.):

1. Add the API key to `Settings` in `opengateway/config.py`.
2. Implement `BaseProvider` in `opengateway/providers/<name>.py`.
3. Add a routing rule in `opengateway/mojo/main.mojo`'s `_select_provider_module`
   **and** in the Python mirror at the bottom of `tests/test_mojo_bridge.py`.
4. Add an entry to the README provider matrix.

The Python bridge dynamically imports the provider module by string
name, so the Mojo layer never needs to know provider-specific code.

## Adding a route

For both servers:

- FastAPI: add a `@app.<method>` decorator in `opengateway/main.py`.
- Mojo: add `router.<method>(path, handler)` in
  `opengateway/mojo/main.mojo`'s `serve()` function.

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
