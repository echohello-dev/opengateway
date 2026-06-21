# Mojo + Python AI Gateway Sketch

> **Status:** Superseded by [architecture.md](./architecture.md) and
> [ADR-002: Mojo API Surface](../adr/002-mojo-api-surface.md).
> Kept here as the original design rationale.

This doc sketches a practical path to building an AI gateway with Python as the control plane and Mojo as an optional performance layer.

## Recommendation

Use Python for the gateway API surface and orchestration, then move only hot paths into Mojo when profiling proves they matter.

That gives you:

- fast iteration on routing, auth, provider support, and policy logic
- access to the Python ecosystem for HTTP, Redis, Postgres, observability, and SDKs
- a clean path to compiled performance where it matters

## Concrete Architecture

### Layers

1. Client layer
   - OpenAI-compatible clients, SDKs, and internal apps
   - Sends requests to a single gateway endpoint

2. Python API layer
   - FastAPI or Starlette HTTP server
   - Request validation and normalization
   - API key auth, tenant lookup, quotas, budgets
   - Provider selection, fallback, retry, and rate-limit policy
   - Request logging, usage accounting, and observability

3. Mojo hot path layer
   - Token counting or prompt shaping
   - Policy evaluation that is CPU-heavy
   - Fast request classification
   - Heuristic routing and scoring

4. Provider layer
   - OpenAI, Anthropic, Azure OpenAI, Bedrock, local vLLM, Ollama, etc.
   - Each provider adapter stays in Python at first

5. State layer
   - Redis for rate limits, budgets, and short-lived caches
   - Postgres for tenants, keys, projects, model maps, audit logs
   - Optional queue for async logging or batch usage aggregation

### Request Flow

1. Client sends an OpenAI-style request to the Python gateway.
2. Python validates auth, tenant, model, and request shape.
3. Python calls the Mojo helper for a hot-path decision.
4. Mojo returns a compact result such as:
   - token estimate
   - route score
   - policy verdict
   - normalized prompt metadata
5. Python selects a provider and applies retries/fallbacks.
6. Python forwards the request to the provider SDK or upstream HTTP endpoint.
7. Python records usage, latency, cost, and errors.

### Why This Split Works

- Gateway logic changes often, so Python keeps the control plane easy to modify.
- Most gateway latency comes from upstream model calls, not local CPU work.
- Mojo is best used where local compute becomes measurable and repeatable.
- You avoid betting the entire gateway on Mojo ecosystem maturity.

## Python vs Mojo vs Rust

### Python

Best for:

- fastest delivery
- mature web and data ecosystem
- provider SDKs and integrations
- observability, migrations, admin tooling

Tradeoffs:

- slower for CPU-heavy local work
- more care needed for concurrency and runtime overhead
- less suitable if you want to push every component into a single compiled binary

### Mojo

Best for:

- high-performance compute with Python interoperability
- AI-adjacent workloads where you want compiled speed
- incremental migration from Python to compiled code

Tradeoffs:

- web/server ecosystem is still young
- production gateway patterns are less mature than Python
- calling Mojo from Python is still early and should be treated as a controlled integration point

### Rust

Best for:

- a fully compiled gateway core
- strong correctness and memory safety
- high-throughput networking and async systems
- long-term standalone services with predictable runtime behavior

Tradeoffs:

- slower development for provider-heavy gateway code
- more engineering overhead for rapid iteration
- Python ecosystem interoperability is possible, but less natural than staying in Python for orchestration

### Practical Verdict

- Choose Python if you want to ship the gateway quickly.
- Choose Mojo if you want to keep Python ergonomics but move selected hot paths to compiled code.
- Choose Rust if you want the whole gateway to be compiled infrastructure from day one and can afford more implementation cost.

For this kind of gateway, the best default is Python first, Mojo second, Rust only if you are deliberately committing to a systems-first gateway.

## Where the Implementation Landed

The sketch above was the early-stage design. The actual implementation
lives at:

- `opengateway/main.py` — FastAPI server (Python, default)
- `opengateway/mojo/main.mojo` — flare server (Mojo, opt-in)
- `opengateway/mojo_bridge/` — synchronous Python entry points
- `tests/test_mojo_bridge.py` — bridge tests
- `tests/mojo/test_router.mojo` — Mojo routing tests (relocated to
  `opengateway/mojo/test_router.mojo` so they can use relative imports)

For the current layering rationale and how to add a provider or
route, see [architecture.md](./architecture.md) and
[ADR-002](../adr/002-mojo-api-surface.md).

## Build Path I Would Use

1. Build the gateway entirely in Python first.
2. Add profiling around request parsing, token counting, and routing.
3. Move one measured hot path into Mojo.
4. Keep the integration boundary narrow and stable.
5. Revisit Rust only if you later want to replace the entire control plane.

## Short Answer

If your goal is a production AI gateway, the best near-term design is:

- Python for HTTP, auth, routing, retries, providers, and state
- Mojo for local compute hot spots
- Rust only if you want to rebuild the whole gateway as systems software

