"""Helpers for calling into the Python bridge from Mojo.

The Mojo HTTP handlers never talk to providers or databases directly.
Every piece of business logic is funnelled through
``opengateway.mojo_bridge``, which exposes a small synchronous surface
the Mojo layer can call without juggling the asyncio event loop.

This module owns:

- A cached reference to the bridge module (imported once at startup).
- Thin wrappers around ``json.dumps`` / ``json.loads`` so handlers can
  move data between Mojo ``String`` values and Python ``dict``s
  without losing readability.
- The standard error envelope used by every handler for non-2xx
  responses.
"""


# `bridge_module` is a lazily-initialised global holding the imported
# Python module. Importing is the only allowed side effect at module
# scope in Mojo — the rest of the helpers are pure functions that
# dispatch through this single import.
comptime bridge_module = _import_bridge()


@always_inline
fn _import_bridge() -> PythonObject:
    var py = Python.import_module("opengateway.mojo_bridge")
    return py


fn json_loads(text: String) -> PythonObject:
    """Parse a JSON string into a Python ``dict`` (via ``json.loads``)."""
    var py_json = Python.import_module("json")
    return py_json.loads(text)


fn json_dumps(obj: PythonObject) -> String:
    """Serialise a Python value to a JSON ``String`` (via ``json.dumps``)."""
    var py_json = Python.import_module("json")
    return String(py_json.dumps(obj))


fn ok_envelope(body: PythonObject) -> PythonObject:
    """Build the ``{"status": 200, "body": ...}`` envelope for the bridge."""
    var py_json = Python.import_module("json")
    return Python.dict(
        {
            "status": 200,
            "body": py_json.dumps(body),
        }
    )


fn error_envelope(status: Int, kind: String, message: String) -> PythonObject:
    """Build a standard error envelope the Mojo handler can serialise.

    The returned dict has shape ``{"status": <int>, "body": <json str>}``
    where ``body`` is the serialised ``{"error": {"message": ..., "type": ...}}``
    payload. The Mojo handler maps the status onto the HTTP response and
    emits the body verbatim.
    """
    var py_json = Python.import_module("json")
    var err = Python.dict(
        {
            "error": Python.dict(
                {"message": message, "type": kind}
            )
        }
    )
    return Python.dict(
        {
            "status": status,
            "body": py_json.dumps(err),
        }
    )
