"""Tests for the in-binary TLS proxy (opengateway.mojo_bridge.tls_proxy).

Integration-style: generates a self-signed cert with the openssl CLI,
serves a trivial cleartext HTTP responder as the upstream, and drives
real TLS clients through the proxy. Skips when openssl is unavailable.
"""

from __future__ import annotations

import shutil
import socket
import ssl
import subprocess
import threading
import time
from typing import Any

import pytest

from opengateway.mojo_bridge.tls_proxy import start_tls_proxy

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl CLI not available")


@pytest.fixture(scope="module")
def self_signed_cert(tmp_path_factory: Any) -> Any:
    import tempfile

    tmp = tempfile.mkdtemp()
    key = f"{tmp}/server.key"
    pem = f"{tmp}/server.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            key,
            "-out",
            pem,
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )
    return pem, key


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _serve_cleartext(port: int, body: bytes, chunks: int = 1) -> threading.Thread:
    """Minimal cleartext HTTP responder; writes the body in ``chunks``
    pieces to exercise the pump's incremental forwarding."""

    def run() -> None:
        srv = socket.create_server(("127.0.0.1", port))
        try:
            conn, _ = srv.accept()
            conn.recv(4096)
            head = (
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            )
            conn.sendall(head)
            step = max(1, len(body) // chunks)
            for i in range(0, len(body), step):
                conn.sendall(body[i : i + step])
                time.sleep(0.01)
            conn.close()
        finally:
            srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def _tls_get(port: int, ca: str) -> bytes:
    # Unverified client: these tests exercise the proxy byte path, not
    # PKI. A self-signed server cert is not a valid CA for chain
    # verification, and a full CA+leaf fixture adds nothing here.
    context = ssl._create_unverified_context()  # noqa: SLF001
    with (
        socket.create_connection(("127.0.0.1", port)) as raw,
        context.wrap_socket(raw, server_hostname="localhost") as tls,
    ):
        tls.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        out = b""
        while True:
            data = tls.recv(4096)
            if not data:
                return out
            out += data


def test_tls_proxy_round_trip(self_signed_cert: Any) -> None:
    pem, key = self_signed_cert
    upstream_port = _free_port()
    proxy_port = _free_port()
    _serve_cleartext(upstream_port, b"hello over tls")
    start_tls_proxy("127.0.0.1", proxy_port, "127.0.0.1", upstream_port, pem, key)
    time.sleep(0.2)

    response = _tls_get(proxy_port, pem)
    assert b"200 OK" in response
    assert response.endswith(b"hello over tls")


def test_tls_proxy_rejects_cleartext(self_signed_cert: Any) -> None:
    pem, key = self_signed_cert
    upstream_port = _free_port()
    proxy_port = _free_port()
    _serve_cleartext(upstream_port, b"nope")
    start_tls_proxy("127.0.0.1", proxy_port, "127.0.0.1", upstream_port, pem, key)
    time.sleep(0.2)

    with socket.create_connection(("127.0.0.1", proxy_port)) as conn:
        conn.sendall(b"GET / HTTP/1.1\r\n\r\n")
        conn.settimeout(2.0)
        try:
            data = conn.recv(256)
        except (ConnectionResetError, BrokenPipeError, TimeoutError):
            # Server aborted the failed handshake without responding —
            # also a valid rejection.
            return
        # TLS alert bytes, not an HTTP response: an HTTP response
        # starts with 'H'.
        assert not data.startswith(b"HTTP")


def test_tls_proxy_incremental_forwarding(self_signed_cert: Any) -> None:
    """A multi-chunk upstream response arrives complete through the pump."""
    pem, key = self_signed_cert
    upstream_port = _free_port()
    proxy_port = _free_port()
    payload = b"x" * 8192
    _serve_cleartext(upstream_port, payload, chunks=8)
    start_tls_proxy("127.0.0.1", proxy_port, "127.0.0.1", upstream_port, pem, key)
    time.sleep(0.2)

    response = _tls_get(proxy_port, pem)
    assert response.endswith(payload)
