"""OpenGateway Mojo entry point.

Hosts the HTTP API surface on top of the flare framework. All business
logic (auth, provider dispatch, upstream calls) is delegated to the
Python bridge in `opengateway.mojo_bridge`. The Mojo layer is responsible
only for HTTP transport, routing, and response serialisation.

Run with:

    pixi run -e mojo mojo run main.mojo

or build a static binary for production:

    pixi run -e mojo mojo build main.mojo -O3 -D ASSERT=none -o opengateway-mojo
"""
from flare.prelude import *
from python import PythonObject, Python

from .router import select_provider_module
from .bridge import bridge_module, json_dumps, json_loads


# ── Handlers ────────────────────────────────────────────────────────────────


def health(req: Request) -> Response:
    """Liveness probe. Returns 200 with a fixed JSON body."""
    return ok_json('{"status":"ok"}')


def chat_completions(req: Request) raises -> Response:
    """OpenAI-compatible chat completions endpoint.

    Accepts the standard OpenAI JSON request shape, delegates validation
    and upstream dispatch to the Python bridge, and returns an
    OpenAI-compatible JSON response.

    Failure modes are mapped to HTTP status codes:

    - 400: empty body, missing fields, malformed JSON, unknown model
    - 401: missing or invalid Authorization header
    - 403: virtual key is not allowed to use the requested model
    - 429: virtual key budget exceeded
    - 502: upstream provider failure
    - 500: unhandled error in the bridge (sanitised response)
    """
    var body_text = req.text()
    if len(body_text) == 0:
        return _json_error(400, "invalid_request_error", "empty request body")

    var auth_header = req.headers.get("authorization")

    var payload = json_loads(body_text)
    if not _has_key(payload, "model"):
        return _json_error(400, "invalid_request_error", "missing field: model")
    if not _has_key(payload, "messages"):
        return _json_error(400, "invalid_request_error", "missing field: messages")

    var model = String(payload["model"])
    var provider_module = select_provider_module(model)
    if provider_module == "":
        return _json_error(400, "invalid_request_error", "unknown model: " + model)

    var result = bridge_module.handle_chat(
        payload,
        auth_header,
        String(provider_module),
    )

    var status = Int(result["status"])
    var body_json = String(result["body"])
    if status == 200:
        return ok_json(body_json)
    return _build_error(status, body_json)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _has_key(obj: PythonObject, key: String) -> Bool:
    try:
        _ = obj[key]
        return True
    except Exception:
        return False


def _build_error(status: Int, body_json: String) -> Response:
    var resp = Response(status=status, reason=_status_reason(status))
    try:
        resp.body = _bytes_from_string(body_json)
        resp.headers.set("Content-Type", "application/json")
    except:
        pass
    return resp^


def _json_error(status: Int, kind: String, message: String) -> Response:
    var body = String(
        Python.dict(
            {
                "error": Python.dict(
                    {"message": message, "type": kind}
                )
            }
        )
    )
    return _build_error(status, json_dumps(body))


@always_inline
def _bytes_from_string(s: String) -> List[UInt8]:
    var out = List[UInt8]()
    var n = s.byte_length()
    if n == 0:
        return out^
    out.resize(n, UInt8(0))
    var src = s.as_bytes()
    var dst = out.unsafe_ptr()
    for i in range(n):
        dst[i] = src[i]
    return out^


# `_status_reason` is exported by `flare.http._server.write` and re-exported
# via the prelude's response module; if it isn't pulled into the prelude in
# the installed flare version, fall back to a small inline mapping here.
fn _status_reason(status: Int) -> String:
    if status == 200:
        return "OK"
    if status == 400:
        return "Bad Request"
    if status == 401:
        return "Unauthorized"
    if status == 403:
        return "Forbidden"
    if status == 404:
        return "Not Found"
    if status == 429:
        return "Too Many Requests"
    if status == 502:
        return "Bad Gateway"
    return "Internal Server Error"


# ── Server entry point ──────────────────────────────────────────────────────


def serve(
    host: String = "0.0.0.0",
    port: Int = 8080,
    num_workers: Int = 4,
) raises:
    """Bind the HTTP server and block until shutdown."""
    var router = Router()
    router.get("/health", health)
    router.post("/v1/chat/completions", chat_completions)

    var addr = SocketAddr.parse(host + ":" + String(port))
    var server = HttpServer.bind(addr)
    print(
        "opengateway (mojo): listening on",
        String(addr),
        "with",
        String(num_workers),
        "workers",
    )
    server.serve(router^, num_workers=num_workers)


def main() raises:
    serve()
