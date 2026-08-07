"""Minimal reproducer for the TLS proxy daemon-thread hang.

Spawns a daemon thread that does TLS accept + recv on a loopback
socket, prints whether recv ever returns data, then exits. Used from
``opengateway/mojo/repro_tls_thread.mojo`` to compare with vs without
``GILReleased`` wrapping the reactor.
"""

from __future__ import annotations

import socket
import ssl
import threading
import time


def repro(timeout_s: float = 5.0) -> dict:
    """Open a TLS listener, accept one connection, report what recv sees.

    Returns a dict with the timeline of events so the caller can see
    exactly where the hang occurs.
    """
    events: list[tuple[str, float]] = []

    def record(name: str) -> None:
        events.append((name, time.time()))

    record("start")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # Path used in tests/test_tls_proxy.py; the test that exercises this
    # helper guarantees the cert exists before calling.
    import os

    if not os.path.exists("/tmp/og-tls-certs/server.pem"):
        os.makedirs("/tmp/og-tls-certs", exist_ok=True)
        import subprocess

        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                "/tmp/og-tls-certs/server.key",
                "-out",
                "/tmp/og-tls-certs/server.pem",
                "-days",
                "1",
                "-nodes",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
            capture_output=True,
        )

    context.load_cert_chain(
        certfile="/tmp/og-tls-certs/server.pem",
        keyfile="/tmp/og-tls-certs/server.key",
    )

    listener = socket.create_server(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    record(f"bound 127.0.0.1:{port}")

    result: dict = {"port": port, "events": []}

    def accept_one() -> None:
        record("accept: waiting for client")
        try:
            raw, _ = listener.accept()
            record("accept: client connected")
            tls = context.wrap_socket(raw, server_side=True)
            record("accept: handshake complete")
            tls.settimeout(timeout_s)
            tls.setblocking(False)
            record("accept: non-blocking set")
            deadline = time.time() + timeout_s
            try:
                while time.time() < deadline:
                    record("accept: recv called")
                    try:
                        data = tls.recv(8192)
                    except ssl.SSLWantReadError:
                        record("accept: SSLWantReadError")
                        time.sleep(0.02)
                        continue
                    except ssl.SSLWantWriteError:
                        record("accept: SSLWantWriteError")
                        time.sleep(0.02)
                        continue
                    except BlockingIOError:
                        record("accept: BlockingIOError")
                        time.sleep(0.02)
                        continue
                    if not data:
                        record("accept: EOF")
                        break
                    record(f"accept: recv {len(data)} bytes")
            finally:
                try:
                    tls.close()
                except Exception:
                    pass
        except Exception as exc:
            record(f"accept: exception {type(exc).__name__}: {exc}")
        finally:
            try:
                listener.close()
            except Exception:
                pass
            record("accept: closed")

    t = threading.Thread(target=accept_one, daemon=True)
    t.start()

    record("client: connecting")
    ctx_client = ssl._create_unverified_context()
    with socket.create_connection(("127.0.0.1", port)) as raw:
        record("client: tcp connected")
        with ctx_client.wrap_socket(raw, server_hostname="localhost") as tls:
            record("client: handshake complete")
            tls.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
            record("client: sent GET")
            # Hard cap on recv so the client cannot deadlock the Mojo
            # call if the server thread is starved.
            tls.settimeout(3.0)
            try:
                data = tls.recv(4096)
                record(f"client: recv {len(data)} bytes")
            except (socket.timeout, ssl.SSLWantReadError) as exc:
                record(f"client: recv timeout: {type(exc).__name__}")
            except Exception as exc:
                record(f"client: recv exception {type(exc).__name__}: {exc}")

    t.join(timeout=2)
    record("done")

    result["events"] = events
    return result
