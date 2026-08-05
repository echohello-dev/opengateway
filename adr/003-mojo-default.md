# ADR-003: Make Mojo on flare the default server

**Status:** Accepted

**Date:** 2026-07-31

**Author:** Johnny Huynh

**Supersedes:** ADR-002 (in part — see "What this changes about ADR-002" below).

---

## Context

ADR-002 (2026-06-20) introduced a Mojo + [flare](https://github.com/ehsanmok/flare) server alongside the FastAPI server and committed FastAPI as the default deployment target. The Mojo path was framed as the edge-binary opt-in:

> For an open-source project, **the FastAPI server is the default**. The Mojo server exists for two reasons: positioning, and a smaller operational shape for managed SaaS.
>
> — `adr/002-mojo-api-surface.md:69-70`

Two months later, after a deeper pass on flare's actual v0.9 surface (HTTP/3, streaming-proxy for SSE, middleware stack, 62 fuzz harnesses, request-id propagation, panic safety, graceful drain, 9M+ fuzz runs, ~242k req/s in their 4-worker benchmark), the original reasoning has eroded:

1. **Framework feature gap is small.** flare covers the HTTP-layer requirements of an LLM gateway end-to-end: typed extractors, middleware, SSE, request streaming, structured logging, Prometheus metrics, request-id propagation, rate limiting, circuit breaker, graceful drain, TLS. The earlier assessment over-weighted gaps that turned out to be solved in v0.7-v0.9.

2. **Ecosystem gap is large.** There is still no Mojo-native Postgres driver, Redis client, or async runtime. Anything stateful has to go through the Python bridge.

3. **The "easy to customise" pitch favours FastAPI.** Every provider SDK in the world is a `pip install` away. The strategy note's "Python first, Mojo second" framing depends on Python staying the primary surface.

4. **The positionally-on-Mojo framing favours the Mojo binary.** Shipping a 30 MB static image in place of a 150 MB `python:3.12-slim`+deps stack is a concrete, demonstrable claim of "we eat our own dog food on the static-binary bet."

This ADR proposes flipping the default: the Mojo binary becomes the production deployment target. FastAPI stays in-tree as the Python-only dev path (`uv run opengateway`). The Python bridge keeps owning everything stateful — providers, auth, settings — and the Mojo layer keeps owning transport. The boundary is unchanged from ADR-002.

## Decision

1. **Default deployment is the Mojo static binary** built from `opengateway/mojo/main.mojo`. `Dockerfile` produces a two-stage image with `mambaorg/micromamba:2.0.5-ubuntu22.04` building the binary in stage 1 and `python:3.12-slim` running it in stage 2.

2. **FastAPI stays in-tree** as `opengateway/main.py`, exposed via the `opengateway` console script for Python-only local dev. It is no longer the production target.

3. **The Python bridge (`opengateway/mojo_bridge/`) is the source of truth** for auth, request validation, provider dispatch, and (eventually) DB-backed virtual keys. The Mojo handler calls one synchronous function — `bridge.handle_chat(payload, auth, provider_module)` — and never catches Python exceptions.

4. **flare is pinned to v0.9.0** (`pixi.toml:27`). The pin gets a follow-up bump to v0.9.x on the next stable tag.

5. ~~Streaming SSE (`stream: true`) is explicitly deferred~~ **Shipped
   2026-08-05 alongside this ADR's implementation.** The bridge gains
   `handle_chat_stream(body, auth, provider_module)`, which validates
   synchronously (so 4xx/5xx fail before SSE headers are written) and
   then spawns a pump thread that feeds OpenAI-shaped SSE frames into a
   bounded queue. The Mojo handler wraps the handle in a
   `PythonQueueSource` `ChunkSource` and serves it via flare's
   `stream_response` (K1 chunked / h2 DATA path). Verified end-to-end
   against a mock upstream (`tests/mock_upstream.py`): 4 incremental
   frames + `data: [DONE]`, correct SSE headers, per-frame latency
   matching the upstream's token cadence.

## What this changes about ADR-002

ADR-002's framing is updated but the layering it documented is unchanged:

| Aspect | ADR-002 (June) | ADR-003 (July) |
|---|---|---|
| Default deployment | FastAPI | Mojo on flare |
| FastAPI's role | Production target | Python-only dev path (`uv run opengateway`) |
| Mojo's role | Edge / binary opt-in | Default |
| Mojo ↔ Python boundary | One sync call to the bridge | Unchanged |
| Provider adapters | Python (httpx async) | Unchanged |
| Streaming SSE | FastAPI only | Both servers (bridge pump thread + `ChunkSource`) |

## Layout

```
opengateway/
├── main.py                   # FastAPI server (Python-only dev path)
├── auth.py                   # Virtual key + root key auth (unchanged)
├── config.py                 # Settings via pydantic-settings
├── router.py                 # Python-side model-to-provider routing
├── providers/                # Unchanged — called by the bridge
│   ├── base.py
│   └── openai.py
├── mojo/                     # Mojo server on flare — default deployment
│   ├── main.mojo             # flare HTTP server + CatchPanic → StructuredLogger → Compress → RequestId → Router stack
│   ├── router.mojo           # Model → provider module routing
│   ├── test_router.mojo
│   └── __init__.mojo
└── mojo_bridge/              # Python side of the bridge (unchanged)
    ├── __init__.py
    ├── chat.py
    ├── stream.py
    └── auth.py
```

## Boundary

The Mojo layer is responsible for:
- HTTP parsing, routing, response serialisation (flare native)
- Middleware composition: `CatchPanic → StructuredLogger → Compress → RequestId → Router` (flare native)
- Connection management: TLS (when configured), keep-alive, graceful drain
- Static-binary deployment, distroless container

The Python bridge is responsible for:
- Auth (`opengateway.mojo_bridge.auth`) — root-key today, DB-backed virtual keys later
- Request validation (`opengateway.mojo_bridge.chat`)
- Provider dispatch and upstream calls (`opengateway.providers.*`)
- Settings, observability metadata, anything stateful

The Mojo handler calls `bridge.handle_chat(payload, auth, provider_module)` and reads `{"status": <int>, "body": <json str>}`. Status maps to the HTTP response code; body is the wire bytes. The Mojo layer never catches a Python exception — exceptions are mapped to envelopes in the bridge.

For streaming, the handler calls `bridge.handle_chat_stream(payload, auth, provider_module)`, which validates synchronously and returns `{"status": 200, "handle": StreamHandle}`. The handle is an opaque `PythonObject` wrapping a bounded `queue.Queue` fed by a background pump thread that drives `provider.chat_stream`; the Mojo side pulls frames through a `ChunkSource` (`PythonQueueSource.next` → `handle.next_chunk(0.5)`) and serves them via flare's `stream_response`. Client disconnect flips the request's `Cancel` token, the source calls `handle.cancel()`, and the pump thread unwinds between frames.

## Spike validation

Bumping flare to v0.9.0 and rebuilding the binary against the existing `opengateway/mojo/` directory produced:

- A **820 KB static binary** at `-O3 -D ASSERT=none` against flare v0.9.0 on macOS arm64. Same builder path produces a ~30 MB distroless Docker image.
- The router test (`opengateway/mojo/test_router.mojo`, 8 tests) compiles and passes.
- The HTTP server boots, binds `127.0.0.1:8080`, and returns `200 OK` on `GET /health`. Verified locally:
  ```
  $ curl -s -i http://127.0.0.1:8080/health
  HTTP/1.1 200 OK
  Content-Type: application/json
  Content-Length: 16
  {"status":"ok"}
  ```
- The Python bridge (`opengateway.mojo_bridge.handle_chat`) is reachable from the Mojo handler via `Python.import_module`. `opengateway/mojo/smoke.mojo` round-tripped a `Python.import_module("opengateway.mojo_bridge")` and printed the module path.
- All pytest cases (`tests/test_proxy.py`, `tests/test_mojo_bridge.py`) continue to pass — 28 tests including 5 streaming cases that drain a real `StreamHandle` against a stub provider (frames + `data: [DONE]` + EOF, plus validation-before-thread-start).
- **End-to-end streaming verified locally** against a mock upstream (`tests/mock_upstream.py`): `POST /v1/chat/completions` with `stream: true` returns `200` with `Content-Type: text/event-stream`, `Transfer-Encoding: chunked`, and 4 incremental frames followed by `data: [DONE]`, with wall-clock time matching the upstream's 250 ms/token cadence (proving frames flow per-token, not buffered).
- Two runtime env issues surfaced during the spike:
  - The Mojo runtime is linked against Python 3.12/3.13 ABI symbols (`Py_NewRef`); Python 3.14 renamed the public symbol and Xcode's system Python 3.9 predates it. The runtime stage of the Dockerfile pins `python:3.12-slim` to match. Locally, point `MOJO_PYTHON_LIBRARY` at a 3.13 dylib (the pixi mojo env ships one).
  - The pre-existing `_provider_class_name` naming convention (`"openai"` → `OpenaiProvider`) never matched the actual `OpenAIProvider` class; the bridge now scans the provider module for a concrete `BaseProvider` subclass instead of deriving a name. Both request paths (streaming and non-streaming) hit this on the first real upstream call, so the fix is load-bearing, not cosmetic.

## Consequences

### Positive

- **Single binary in production.** `opengateway:mojo` is a two-stage image built once, scanned once, deployed once. One CVE stream instead of `fastapi + pydantic + httpx + asyncpg + redis + structlog + uvicorn + starlette + anyio + ...`.
- **~30 MB image, ~50 ms cold start, no `pip install` in the container.** These were the original ADR-002 framing for the Mojo path; making it default means every deployment gets them, not just the edge case.
- **flare's middleware stack is now in production from day one.** `CatchPanic` sanitises handler raises to 500; `RequestId` injects / propagates `X-Request-Id`; `Router` carries typed extractors. The previous default (FastAPI with no middleware at all) was operationally thinner.
- **Mature HTTP semantics.** flare 0.9 includes HTTP/1.1 + HTTP/2 + HTTP/3 over QUIC, fuzzed through 62 harnesses over 9M+ runs, with a typed streaming-proxy surface that's the designed-for shape for an LLM gateway.
- **"Easy to customise" is preserved.** Anyone who wants to add a provider, change auth, or add a route can still `uv pip install -e ".[dev]"`, run the FastAPI dev server with a debugger attached, edit `opengateway/providers/<name>.py`, and the same Python code is what the bridge calls in production.

### Negative

- **Two servers to maintain.** Routing, middleware, error mapping all exist in both `opengateway/main.py` and `opengateway/mojo/main.mojo`. Drift is a real risk; the `test_routing_rules_match_mojo_router` test in `tests/test_mojo_bridge.py` is the first explicit guard, and the Mojo router logic now lives inline in `main.mojo` (the standalone `router.mojo` was the prior separate-file shape). The drift guard covers model-name routing only; full request-shape parity is a follow-up.
- **Streaming SSE frames carry the normalised `ChatResponse` shape**, not the raw upstream `chat.completion.chunk` wire shape. This matches the FastAPI dev server (both call `chunk.model_dump_json()`), so the two servers are consistent, but a client that pattern-matches on OpenAI's exact chunk envelope (e.g. reading `choices[0].delta.content`) will need the flattened `content` field instead. Passing raw provider chunks through untouched is a follow-up that requires reshaping `BaseProvider.chat_stream`.
- **The streaming pull loop blocks the flare worker between frames.** `PythonQueueSource.next` calls `handle.next_chunk(0.5)` — a blocking `queue.get` — so a flare worker is occupied by one streaming request at a time, the same blocking profile as the non-streaming path (`asyncio.run` inside the bridge). `num_workers` must be sized for concurrent streaming load. The flare-native fix (an `AsyncChunkSource` over a real fd, per the `serve_streaming` surface) needs a Mojo async runtime or a UDS hop and is a follow-up.
- **Maturity risk on flare.** flare is 4 months old, 4 contributors, single maintainer, ~40 stars. The Mojo runtime is in `1.0.0b2` (beta). Both are young, both have shipped their first backwards-compatible releases, both are usable in production today. The hedge against immaturity is the FastAPI dev path: if either breaks, contributors have a stable Python surface to develop against.
- **Build-time cost.** The Mojo compile of `opengateway/mojo/main.mojo` against flare v0.9.0 takes ~6 minutes on macOS arm64 in CI cold cache. This is a one-time cost; rebuilds are incremental. But it does move the CI graph forward by 6 minutes, which is on the borderline of acceptable for a PR-check.
- **The Python bridge still depends on the mojopkg surface for streaming.** When the SSE follow-up lands, the bridge will own the Python-side streamer and the Mojo side will own the FrameMux ↔ `UpstreamChunkSource` plumbing. That's a non-trivial wiring job and is documented as a follow-up.

### Neutral

- **`python:3.12-slim` in the runtime stage.** Even with the Mojo binary as the entrypoint, the runtime stage pulls `python:3.12-slim` because the bridge imports the provider adapters. The image stays small (the binary is the dominant artifact) but Python is in the image for the bridge's lifetime. Trimming this further requires Mojo-native provider SDKs (a separate, much-larger effort).
- **The strategy-note "Python first, Mojo second" line is partially walked back.** The framing now reads: "Python providers, Mojo transport." Python is still the surface for everything stateful; Mojo wins the transport.

## Follow-ups

Each follow-up is a one-page issue. None blocks this ADR.

1. ~~**`stream: true` on the Mojo server.**~~ **Shipped** with this ADR's implementation: `opengateway/mojo_bridge/stream.py` (validation + pump thread + bounded queue) and `PythonQueueSource` in `opengateway/mojo/main.mojo` (reactor-side pull). e2e-verified against `tests/mock_upstream.py`. The remaining upgrade is the flare-native `serve_streaming` / `UpstreamChunkSource` shape over a UDS (removes the per-frame blocking pull and per-worker occupancy); that refactor is tracked separately and is invisible to clients.

2. ~~**Full middleware stack.**~~ **Partially shipped:** `CatchPanic → StructuredLogger → Compress → RequestId → Router` is wired in `opengateway/mojo/main.mojo`. `Metrics` remains open (needs a `MetricsRegistry` configuration decision and a `/metrics` route).

3. **Rate limiting.** `RateLimit[Inner]` middleware with a token-bucket admission gate. Per-process only; for distributed rate limiting we still need Redis (which means a Mojo client or back through the bridge). Estimate: half a day for per-process.

4. **TLS termination.** Use `TlsAcceptor` over OpenSSL, cert reload via `acceptor.reload()`. The Dockerfile needs to ship `build/libflare_tls.so` (or link statically if that's available — needs a flare contribution). Estimate: 1 day.

5. **DB-backed virtual keys.** A real Postgres driver in Mojo doesn't exist; either keep auth through the Python bridge or contribute one. The Mojo-side auth module grows a `State[AuthBridge]` extractor. Estimate: at minimum a week of focused work, plus a maintained Postgres driver.

6. **HTTP/3 enablement.** `HttpServer.bind_with_http3` adds a UDP listener for h3 over QUIC. Should be a config flag, off by default until QUIC is battle-tested at scale. Estimate: 1 day once we decide to ship it.

7. **CI parallelism for the Mojo build.** The 6-minute compile is acceptable but eats CI time. Pre-compile `flare + json + openai_bridge` into a `.mojoc` package in CI and pull it as a build artifact rather than recompiling from source. Estimate: 1-2 days; this is a significant CI improvement.

8. **Raw chunk pass-through for streaming.** The current SSE frames carry the normalised `ChatResponse` JSON. Passing the provider's raw `chat.completion.chunk` through untouched (so clients see the exact upstream envelope) requires reshaping `BaseProvider.chat_stream` to yield raw payloads. Estimate: half a day, plus a test-matrix decision on which providers guarantee which chunk shape.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep FastAPI as default | Original ADR-002 reasoning. Now overturned by the v0.9 feature survey; the operational wins are too large to leave on the opt-in path. |
| Pure Mojo server (no Python bridge) | Provider SDK ecosystem is Python-native; reimplementing `openai-python`, `anthropic-python`, `boto3` in Mojo is multi-month work per provider. The bridge keeps Mojo on the transport and Python on the business logic, which is the layering ADR-002 designed and this ADR preserves. |
| Pure Python (FastAPI only) | Loses the static-binary differentiator. 150 MB image, 1.5 s cold start, eight-package CVE stream. The strategy note's positioning claim becomes aspirational rather than shipped. |
| Switch to Rust (axum/actix) | Same static-binary benefits but loses the "easy to customise" pitch (no PyPI, no provider SDKs) and Mojo's positioning is already in production. |
| Wait for Modular's async runtime + Mojo Postgres driver | The spike validated the Mojo server works today; deferring doesn't buy anything except more waiting. The bridge hedges the Mojo-ecosystem gaps without blocking the deployment-default flip. |

## References

- [ADR-002: Mojo (flare) for the API Surface](./002-mojo-api-surface.md)
- [ADR-001: API Key Format](./001-api-key-format.md)
- [flare v0.9.0 release notes](https://github.com/ehsanmok/flare/releases/tag/v0.9.0)
- [flare features inventory](https://github.com/ehsanmok/flare/blob/v0.9.0/docs/features.md)
- [flare streaming-proxy example](https://github.com/ehsanmok/flare/blob/v0.9.0/examples/advanced/streaming_proxy.mojo) — the design template for the SSE follow-up
- [flare openai_sse_front example](https://github.com/ehsanmok/flare/blob/v0.9.0/examples/advanced/openai_sse_front.mojo) — the SSE-shape template for the streaming follow-up
- [Mojo v1.0.0b2 release notes](https://mojolang.org/releases/v1.0.0b2/) — Python interop surface, `fn` removal, `Int(py=...)` keyword form
- [docs/architecture.md](../docs/architecture.md) — runtime layout (will be updated alongside this ADR)
- [docs/operations.md](../docs/operations.md) — production-shape ops notes (will be updated alongside this ADR)