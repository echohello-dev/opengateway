"""Minimal reproducer for the Mojo-runtime × stdlib-ssl daemon-thread hang.

Build:
    pixi run -e mojo mojo build -I . opengateway/mojo/repro_tls_thread.mojo \\
        -o /tmp/repro-tls

Run, comparing the two scenarios by toggling ``WITH_GILRELEASED`` env:

    MOJO_PYTHON_LIBRARY=$PWD/.pixi/envs/mojo/lib/libpython3.13.dylib \\
    PYTHONPATH=. \\
        /tmp/repro-tls               # Mojo holds the GIL between calls
    MOJO_PYTHON_LIBRARY=$PWD/.pixi/envs/mojo/lib/libpython3.13.dylib \\
    PYTHONPATH=. WITH_GILRELEASED=1 \\
        /tmp/repro-tls               # main thread releases GIL after init

The Python side (opengateway.mojo_bridge._repro_tls.repro) opens a TLS
listener on a random loopback port, spawns a daemon thread that does
accept + handshake + recv, and connects a TLS client to itself. The
output is a timeline of events so you can see where the hang is.

A healthy run produces 10+ events ending with ``done``. A hung run
prints the first 5–6 events and then ``done`` from the timeout.
"""

from std.python import Python, PythonObject
from std.python._cpython import GILReleased
from std.os import getenv


def main() raises:
    var py = Python()
    var mod = Python.import_module("opengateway.mojo_bridge._repro_tls")
    var with_gil = getenv("WITH_GILRELEASED").byte_length() > 0
    print(
        "repro-tls: "
        + ("WITH GILReleased" if with_gil else "WITHOUT GILReleased"),
        flush=True,
    )

    if with_gil:
        with GILReleased(py):
            _run_repro(mod)
    else:
        _run_repro(mod)


def _run_repro(mod: PythonObject) raises:
    var result = mod.repro(5.0)
    var events = result["events"]
    print("events:", flush=True)
    for ev in events:
        var name = String(py=ev[0])
        var ts = Float64(py=ev[1])
        print("  ", ts, name, flush=True)