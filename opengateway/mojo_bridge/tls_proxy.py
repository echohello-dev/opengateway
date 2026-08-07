"""In-binary TLS termination for the Mojo server.

flare v0.9's server-side TLS surface is handshake-only (``TlsAcceptor``
+ ``handshake_fd``); the data path (``SSL_read`` / ``SSL_write`` in the
reactor) is a deferred upstream follow-up, so the Mojo binary cannot
terminate TLS natively today. This module is the in-binary stand-in:
a stdlib ``ssl`` listener that accepts TLS on the public port and
proxies bytes to the cleartext flare listener on loopback.

Design: thread-per-connection blocking pump, two threads per
connection (one per direction). The reactor-native replacement (flare
``STATE_TLS_HANDSHAKE`` + server-side read/write FFI) stays an upstream
follow-up; when it lands this module is deleted and ``main.mojo``
binds TLS directly.

Concurrency note: the pump threads need the GIL to call into the
``ssl`` module. ``main.mojo`` wraps the reactor in ``GILReleased`` so
these threads self-schedule while the Mojo reactor is blocked.
"""

from __future__ import annotations

import contextlib
import logging
import socket
import ssl
import threading

logger = logging.getLogger("opengateway.mojo_bridge.tls_proxy")

_BUF = 64 * 1024


def start_tls_proxy(
    listen_host: str,
    listen_port: int,
    target_host: str,
    target_port: int,
    cert_file: str,
    key_file: str,
) -> threading.Thread:
    """Start the TLS-terminating proxy on a daemon thread.

    Returns the acceptor thread. The thread (and every connection
    thread it spawns) is a daemon, so process exit is owned by the
    Mojo reactor, not by this proxy.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)

    listener = socket.create_server((listen_host, listen_port), reuse_port=False)
    listener.listen()

    thread = threading.Thread(
        target=_accept_loop,
        args=(listener, context, target_host, target_port),
        name="opengateway-tls-proxy",
        daemon=True,
    )
    thread.start()
    return thread


def _accept_loop(
    listener: socket.socket,
    context: ssl.SSLContext,
    target_host: str,
    target_port: int,
) -> None:
    while True:
        try:
            client, _ = listener.accept()
        except OSError:
            logger.exception("tls proxy: accept failed")
            continue
        threading.Thread(
            target=_handle,
            args=(client, context, target_host, target_port),
            name="opengateway-tls-conn",
            daemon=True,
        ).start()


def _handle(
    client: socket.socket,
    context: ssl.SSLContext,
    target_host: str,
    target_port: int,
) -> None:
    """Hand a single TLS connection off to two blocking pump threads."""
    try:
        tls_client = context.wrap_socket(client, server_side=True)
    except (ssl.SSLError, OSError):
        client.close()
        return
    try:
        upstream = socket.create_connection((target_host, target_port))
    except OSError:
        logger.exception("tls proxy: failed to reach cleartext target")
        tls_client.close()
        return

    # Client -> upstream runs on this thread; upstream -> client runs
    # on the forwarder thread. A slow client cannot stall the upstream
    # drain, which matters for SSE where the server writes far more
    # than the client sends.
    forwarder = threading.Thread(
        target=_pump,
        args=(tls_client, upstream),
        name="opengateway-tls-fwd",
        daemon=True,
    )
    forwarder.start()
    _pump(upstream, tls_client)
    forwarder.join(timeout=5)
    tls_client.close()
    upstream.close()


def _pump(source: socket.socket, sink: socket.socket) -> None:
    """Copy bytes from ``source`` to ``sink`` until EOF or error.

    On source EOF, half-closes the sink's write side so the peer sees
    a clean FIN (important for SSE: the upstream's end-of-stream must
    reach the client without tearing down the reverse direction
    first).
    """
    try:
        while True:
            data = source.recv(_BUF)
            if not data:
                break
            sink.sendall(data)
    except OSError:
        pass
    finally:
        with contextlib.suppress(OSError):
            sink.shutdown(socket.SHUT_WR)
