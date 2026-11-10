# Configuration

Everything is environment variables or `.env`. The README shows the quick paths; this page is the full reference.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ROOT_KEY` | `sk-root-change-me` | Admin key with full access. **Replace before deploying.** |
| `OPENAI_API_KEY` | _(unset)_ | Upstream key for `gpt-*` and `openai/*`. |
| `ANTHROPIC_API_KEY` | _(unset)_ | Upstream key for `claude-*` and `anthropic/*`. |
| `ROUTES_JSON` | _(unset)_ | JSON array of `RouteRule` objects, see [Routing table](#routing-table). |
| `DATABASE_URL` | `postgresql://...` | Tenants, keys, audit logs. |
| `REDIS_URL` | `redis://...` | Rate limits and short-lived caches. |
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8080` | Bind port. |
| `WORKERS` | `1` | uvicorn workers (Python only). |
| `DEBUG` | `false` | Reload on file changes. |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `REQUIRE_AUTH` | `true` | Reject requests without a valid `Authorization` header. |

API keys follow [`sk-og-{token}`](../adr/001-api-key-format.md), the same prefix shape as OpenAI, branded to OpenGateway.

## Routing table (`ROUTES_JSON`)

Pin a model to a primary provider with optional fallback, plus pricing for the cost cap:

```bash
ROUTES_JSON='[
  {
    "model": "gpt-4o-mini",
    "primary": "openai",
    "input_price_per_1k": 0.00015,
    "output_price_per_1k": 0.0006,
    "max_output_tokens": 16384
  },
  {
    "model": "gpt-4o",
    "primary": "openai",
    "fallback": "anthropic",
    "input_price_per_1k": 0.0025,
    "output_price_per_1k": 0.01,
    "max_output_tokens": 4096
  }
]'
```

- `model`: exact match against the request body.
- `primary` / `fallback`: short provider name (`openai`, `anthropic`) or full module path (`opengateway.providers.openai`).
- Pricing fields are USD per 1k tokens. They drive the per-key `max_cost_usd` cap (below); if unset, the cap is not enforced.
- `max_output_tokens`: ceiling used when the request omits `max_tokens`. Caps the worst-case completion cost.

When `ROUTES_JSON` is unset, the bridge falls through to the legacy prefix-based routing (`gpt-*` to OpenAI, `claude-*` to Anthropic, `bedrock/*` to Bedrock). Drift between the Python bridge and the Mojo router is guarded by `tests/test_mojo_bridge.py::test_routing_rules_match_mojo_router`.

## Per-key USD cost cap

Set `max_cost_usd` on a virtual key (column added to the `virtual_keys` table). The bridge estimates the upstream cost of each request before calling the provider:

```
estimate = prompt_chars / 4 × input_price + max_tokens × output_price
```

When `budget_used + estimate > max_cost_usd`, the request is rejected with `429 rate_limit_error` before any upstream call. Over-estimation is the right bias for a cap. The cap is independent from the token-denominated `max_budget` field (ADR-003 §166), so set both, set either, or set neither.

## Provider fallback

When the primary provider returns a retryable failure (`5xx`, `429`, connection / timeout), the bridge retries the request against `fallback` once. Non-retryable failures (4xx other than 429) surface immediately: the request is broken, not the provider.

Streaming falls back only before the first frame is queued. Mid-stream errors log a warning and emit the canonical `[DONE]` terminator; the client sees a clean stream end, not a silent provider swap mid-flight.

## TLS termination (in-binary)

Set `TLS_CERT_FILE` and `TLS_KEY_FILE` (PEM-encoded) to terminate TLS inside the Mojo binary via flare's reactor-side TLS state machine, no sidecar and no edge LB. When unset, the listener accepts cleartext on the loopback address so an LB can terminate TLS in front. The `TLS_PORT` env var is unused; the listener binds on `PORT`.

```bash
$ TLS_CERT_FILE=./server.pem TLS_KEY_FILE=./server.key ./og-tls3
opengateway (mojo): HTTPS on 127.0.0.1:8080 with 1 workers

$ curl --cacert ./server.pem --resolve localhost:8080:127.0.0.1 \
    https://localhost:8080/health
{"status":"ok"}
```

> **Self-signed cert gotcha.** The in-binary TLS path requires the cert subject to match the hostname curl uses. Generate the cert with `CN=localhost` (not `CN=127.0.0.1`) and use `--resolve localhost:8080:127.0.0.1` so the cert verifies. Hitting `https://127.0.0.1:8080/health` directly will exit code 60 silently under `curl -s` and look like a hang.

## Demo without an API key (mock upstream)

No OpenAI key? The repo ships a mock SSE upstream so the full path (gateway to provider to streaming client) runs offline:

```bash
$ python tests/mock_upstream.py 9100 &
mock upstream on 127.0.0.1:9100
```

Then set these in `.env` instead of a real key:

```bash
OPENAI_API_KEY=sk-mock-local
OPENAI_BASE_URL=http://127.0.0.1:9100/v1
```

Restart the gateway and hit `/v1/chat/completions` as in the README. The mock replies `"Hello, streaming world!"`, or four SSE frames when `"stream": true`. Works with both servers.
