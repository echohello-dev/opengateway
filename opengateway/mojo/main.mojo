"""OpenGateway Mojo entry point — single static-binary deployment.

Hosts the OpenAI-compatible ``/v1/chat/completions`` endpoint on top of
flare v0.9. Transport, routing, request-id propagation, structured
logging, content negotiation, panic safety, and graceful drain are all
native to flare.

Provider HTTP calls, auth validation, and request-shape validation live
in the Python bridge (``opengateway.mojo_bridge``). The boundary for the
non-streaming path is a single synchronous function call
(``bridge.handle_chat``) that returns an envelope dict. The streaming
path (``stream: true``) calls ``bridge.handle_chat_stream``, which
spawns a background pump thread that feeds OpenAI-shaped SSE frames
into a bounded queue; the Mojo reactor pulls one frame per writable
edge through the ``PythonQueueSource`` ``ChunkSource`` below, with the
queue's maxsize coupling upstream reads to downstream drain.

Run:

    pixi run -e mojo mojo run opengateway/mojo/main.mojo

or build a static binary for production:

    pixi run -e mojo mojo build opengateway/mojo/main.mojo \\
        -O3 -D ASSERT=none -o dist-mojo/opengateway-mojo
"""
from std.collections import Optional

from flare.prelude import (
    CatchPanic,
    Compress,
    HttpServer,
    Request,
    RequestId,
    Response,
    Router,
    ok,
)
from flare.http import (
    Cancel,
    ChunkSource,
    StructuredLogger,
    stream_response,
)
from flare.net import SocketAddr

from std.python import Python, PythonObject


# ── Bridge (lazily imported Python module) ──────────────────────────────────


@always_inline
def _import_bridge() raises -> PythonObject:
    return Python.import_module("opengateway.mojo_bridge")


# ── Helpers ────────────────────────────────────────────────────────────────


@always_inline
def _has_key(obj: PythonObject, key: String) -> Bool:
    try:
        _ = obj[key]
        return True
    except Exception:
        return False


@always_inline
def _json_loads(text: String) raises -> PythonObject:
    return Python.import_module("json").loads(text)


def _ok_json_from_string(s: String) raises -> Response:
    var resp = Response(status=200)
    resp.body = _string_to_bytes(s)
    resp.headers.set("Content-Type", "application/json")
    return resp^


def _build_error(status: Int, body_json: String) raises -> Response:
    var resp = Response(status=status)
    resp.body = _string_to_bytes(body_json)
    resp.headers.set("Content-Type", "application/json")
    return resp^


def _json_error(status: Int, kind: String, message: String) raises -> Response:
    var py_json = Python.import_module("json")
    var body = py_json.dumps(
        Python.dict(error=Python.dict(message=message, type=kind))
    )
    return _build_error(status, String(body))


@always_inline
def _string_to_bytes(s: String) raises -> List[UInt8]:
    var out = List[UInt8]()
    var n = s.byte_length()
    out.resize(n, UInt8(0))
    var src = s.as_bytes()
    var dst = out.unsafe_ptr()
    for i in range(n):
        dst[i] = src[i]
    return out^


# ── Provider routing (mirror of opengateway.mojo.router) ──────────────────


def _select_provider_module(model: String) -> String:
    if model.startswith("gpt-") or model.startswith("openai/"):
        return "opengateway.providers.openai"
    if model.startswith("claude-") or model.startswith("anthropic/"):
        return "opengateway.providers.anthropic"
    if model.startswith("bedrock/") or model.startswith("amazon."):
        return "opengateway.providers.bedrock"
    return ""


# ── Streaming chunk source ──────────────────────────────────────────────────


struct PythonQueueSource(ChunkSource, Copyable, Movable):
    """A ``ChunkSource`` that pulls SSE frames from the Python bridge.

    Holds the ``StreamHandle`` returned by
    ``bridge.handle_chat_stream``. Each ``next`` call blocks up to
    500 ms in ``handle.next_chunk`` (a ``queue.get`` that releases the
    GIL), which matches the blocking profile of the non-streaming
    path: a flare worker is occupied by one request at a time either
    way. Between pulls the source re-checks the cancel token, so a
    client disconnect or request deadline ends the stream and signals
    the pump thread to stop producing.
    """

    var handle: PythonObject

    def __init__(out self, var handle: PythonObject):
        self.handle = handle^

    def next(mut self, cancel: Cancel) raises -> Optional[List[UInt8]]:
        while True:
            if cancel.cancelled():
                try:
                    _ = self.handle.cancel()
                except:
                    pass
                return Optional[List[UInt8]]()
            var result = self.handle.next_chunk(0.5)
            var code = Int(py=result[0])
            if code == 2:
                return Optional[List[UInt8]]()
            var frame = String(py=result[1])
            if frame.byte_length() == 0:
                continue
            return Optional[List[UInt8]](_string_to_bytes(frame))


# ── Routes ──────────────────────────────────────────────────────────────────


def health(req: Request) raises -> Response:
    var resp = ok('{"status":"ok"}\n')
    resp.headers.set("Content-Type", "application/json")
    return resp^


def chat_completions(req: Request) raises -> Response:
    """OpenAI-compatible chat completions — dispatch + SSE.

    Both variants share the same auth / validation path. Non-streaming
    returns the bridge envelope mapped onto an HTTP response; streaming
    (``stream: true``) starts the bridge pump thread and serves the
    queue through ``stream_response`` with the canonical SSE headers.

    The Mojo layer never catches Python exceptions: the bridge returns
    an envelope ``{"status": <int>, "body": <json str>}`` (or
    ``{"status": 200, "handle": StreamHandle}`` for streaming) that maps
    cleanly onto an HTTP response.
    """
    var body_text = req.text()
    if body_text.byte_length() == 0:
        return _json_error(400, "invalid_request_error", "empty request body")

    var auth_header = req.headers.get("authorization")

    var payload = _json_loads(body_text)
    if not _has_key(payload, "model"):
        return _json_error(400, "invalid_request_error", "missing field: model")
    if not _has_key(payload, "messages"):
        return _json_error(
            400, "invalid_request_error", "missing field: messages"
        )

    var model = String(py=payload["model"])
    var provider_module = _select_provider_module(model)
    if provider_module == "":
        return _json_error(
            400, "invalid_request_error", "unknown model: " + model
        )

    var bridge = _import_bridge()

    if _wants_stream(payload):
        var stream_env = bridge.handle_chat_stream(
            payload, auth_header, provider_module
        )
        var stream_status = Int(py=stream_env["status"])
        if stream_status != 200:
            return _build_error(
                stream_status, String(py=stream_env["body"])
            )
        var source = PythonQueueSource(stream_env["handle"])
        var resp = stream_response[PythonQueueSource](source^, 200)
        resp.headers.set("Content-Type", "text/event-stream")
        resp.headers.set("Cache-Control", "no-cache")
        resp.headers.set("X-Accel-Buffering", "no")
        return resp^

    var envelope = bridge.handle_chat(payload, auth_header, provider_module)

    var status = Int(py=envelope["status"])
    var body_json = String(py=envelope["body"])
    if status == 200:
        return _ok_json_from_string(body_json)
    return _build_error(status, body_json)


@always_inline
def _wants_stream(payload: PythonObject) raises -> Bool:
    if not _has_key(payload, "stream"):
        return False
    var s = String(py=payload["stream"])
    return s == "True" or s == "true"


# ── Server entry point ──────────────────────────────────────────────────────


def serve(
    host: String = "0.0.0.0",
    port: Int = 8080,
    num_workers: Int = 4,
) raises:
    """Bind the HTTP server and block until shutdown.

    Middleware ordering (outside-in):

    - CatchPanic: convert any raise in the inner stack to a sanitised 500.
    - StructuredLogger: one JSON-per-line log record per response.
    - Compress: gzip / brotli content negotiation on buffered bodies.
      Streaming responses pass through untouched (``len(resp.body)``
      is zero when ``body_stream`` is set, below the 1024-byte
      minimum).
    - RequestId: inject / propagate ``X-Request-Id``; close to the
      router so the id propagates through every header + log line.
    - Router: the application dispatcher.

    ``Metrics`` and ``RateLimit`` remain ADR-003 follow-ups: both need
    per-process configuration (registry, bucket sizing) that is worth
    a separate change rather than folding in here.
    """
    var router = Router()
    router.get("/health", health)
    router.post("/v1/chat/completions", chat_completions)

    var stack = CatchPanic(
        StructuredLogger(
            Compress(RequestId(router^)),
        )
    )

    var addr = SocketAddr.parse(host + ":" + String(port))
    var server = HttpServer.bind(addr)

    print(
        "opengateway (mojo): listening on",
        String(addr),
        "with",
        String(num_workers),
        "workers",
    )
    server.serve(stack^, num_workers=num_workers)


def main() raises:
    serve(host="127.0.0.1", port=8080, num_workers=1)