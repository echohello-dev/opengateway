# ADR-002: Mojo (flare) for the API Surface

**Status:** Accepted

**Date:** 2026-06-20

**Author:** Johnny Huynh

---

## Context

OpenGateway's strategy note (`Notes/2026-05-01 - OpenGateway AI
Gateway Research and Strategy.md:19, 55`) committed to "Python first,
Mojo second, Rust only if committing to systems-first infrastructure"
and positioned the gateway against LiteLLM (Python) and Bifrost (Go)
on the axis of "easy to customise."

Until now OpenGateway has shipped only the Python FastAPI server
(`opengateway/main.py`). We need to decide whether and how to add a
Mojo-based API surface, and what the boundary with Python looks like.

## Decision

We will add a Mojo + flare HTTP server (`opengateway/mojo/main.mojo`)
that owns the API surface and delegates all business logic to the
Python bridge (`opengateway/mojo_bridge/`). The Python FastAPI server
remains the default deployment target and continues to receive bug
fixes and provider additions.

## Layout

```
opengateway/
├── main.py                   # FastAPI server (default)
├── mojo/
│   ├── main.mojo             # flare HTTP server
│   ├── router.mojo           # model → provider module routing
│   ├── bridge.mojo           # PythonObject helpers + envelope
│   ├── test_router.mojo      # Mojo-side routing tests
│   └── __init__.mojo
├── mojo_bridge/
│   ├── __init__.py           # handle_chat, health_check, authenticate
│   ├── chat.py               # sync wrapper around async providers
│   └── auth.py               # root-key validation
├── providers/                # unchanged (Python)
│   ├── base.py
│   └── openai.py
├── auth.py                   # unchanged (Python)
└── config.py                 # extended with openai_api_key, anthropic_api_key
```

## Boundary

The Mojo layer is responsible for:
- HTTP parsing, routing, response serialisation
- Middleware composition (Logger, RequestId, Compress, CatchPanic, Cors)
- Connection management (TLS, keep-alive, graceful drain)
- Static binary deployment

The Python bridge is responsible for:
- Auth (`opengateway.mojo_bridge.auth`)
- Request validation (`opengateway.mojo_bridge.chat`)
- Provider dispatch and upstream calls (`opengateway.providers.*`)
- Settings and observability

The Mojo handler calls `bridge_module.handle_chat(payload, auth, module)`
which returns an envelope dict `{"status": <int>, "body": <json str>}`
so the Mojo layer never catches Python exceptions itself.

## Consequences

### Positive

- **Positioning realised.** "Bifrost is Go. OpenGateway is Python/Mojo
  - easier to customise" is now a concrete shipping claim, not a
  roadmap line.
- **Operational shape.** A static binary is dramatically easier to
  ship, scan, and scale for managed SaaS (Phase 3 in the strategy).
- **Single CVE stream.** One binary to patch instead of
  `fastapi + pydantic + httpx + asyncpg + redis + structlog + uvicorn + ...`.
- **Cold start.** <50 ms vs ~1.5 s for FastAPI — material for Lambda
  and edge deployments.
- **Compiler-checked API contract.** flare's typed extractors
  (`PathInt`, `Json[T]`, `HeaderStr`) give compile-time guarantees on
  request shape; Pydantic can only validate at runtime.

### Negative

- **Two servers to maintain.** Routing, middleware, error mapping all
  exist in both `opengateway/main.py` and `opengateway/mojo/main.mojo`.
  Drift is a real risk; the `tests/test_mojo_bridge.py::_route_model`
  test is the first explicit guard.
- **Limited Mojo ecosystem.** No asyncpg equivalent, no SQLAlchemy,
  no Alembic. Anything stateful goes through the Python bridge.
- **Bridge cost.** Every `bridge.handle_chat` call crosses the
  Mojo ↔ CPython boundary, which is not free. We accept this because
  the dominant latency is upstream LLM calls, not local dispatch.
- **Maturity risk.** flare is 4 months old, 3 contributors, single
  maintainer. Betting the API surface on a young framework is a real
  call. Mitigated by keeping FastAPI as the default server.

### Neutral

- **PythonObject bridge.** Every Python dependency (`asyncpg`,
  `redis`, `httpx`, `structlog`) is reachable from Mojo via
  `Python.import_module("name")`. We pay the CPython cost per call
  but don't lose access to the ecosystem.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Pure Mojo server (no Python bridge) | Loses asyncpg/redis/httpx; need to reimplement async DB drivers in Mojo. |
| Pure Python (FastAPI only) | Doesn't realise the strategy-note positioning. Larger container, slower cold start. |
| Pure Rust (axum/actix) | Same positioning benefit as Mojo but loses "easy to customise" story (smaller Rust ecosystem than Python for provider SDKs). |
| Mojo for providers, Python for HTTP | Inverts the layering. Provider code is network-bound (httpx) — Mojo wins nothing. HTTP server is CPU-bound on parsing/routing — Mojo wins. |
| Wait for Mojo to mature further | The strategy note already commits to Mojo as a positioning pillar. Waiting defers the differentiator indefinitely. |

## References

- [flare HTTP framework](https://github.com/ehsanmok/flare)
- [OpenGateway strategy note](https://github.com/johnnyhuy/one-obsidian/blob/main/Notes/2026-05-01%20-%20OpenGateway%20AI%20Gateway%20Research%20and%20Strategy.md)
- [ADR-001: API Key Format](./001-api-key-format.md)
- [docs/architecture.md](./architecture.md)
- [docs/mojo-python-ai-gateway.md](./mojo-python-ai-gateway.md)
- [docs/release-process.md](./release-process.md)
