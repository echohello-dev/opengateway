# syntax=docker/dockerfile:1.7

# ── Stage 1: build the Mojo static binary ────────────────────────────────────
# `max-nightly` provides the Mojo toolchain. flare is built from a pinned
# git tag via pixi-build so the image is reproducible.
FROM mambaorg/micromamba:2.0.5-ubuntu22.04 AS builder

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Copy only what pixi needs to resolve the environment, then build.
COPY pixi.toml pixi.lock* ./
RUN micromamba install -y -n base -c https://conda.modular.com/max-nightly -c conda-forge pixi \
    && pixi install -e mojo \
    # Build flare's rustls QUIC cdylib while we have cargo in the env
    # (ADR-003 follow-up #6: HTTP/3 needs it). Cheap on repeat builds —
    # cargo's incremental + the script's atomic install only touch the
    # image when flare's rustls source or Cargo.lock changes.
    && pixi run -e mojo rustls-build \
    && pixi run -e mojo mojo build opengateway/mojo/main.mojo \
        -O3 -D ASSERT=none \
        -o /src/opengateway-mojo

# Copy the Python source the binary needs at runtime (provider
# adapters, auth, settings). The bridge imports them by package name.
COPY opengateway/ /src/opengateway/

# Strip Python bytecode caches from the bridge source so the runtime
# image is smaller (cpython will regenerate them on import).
RUN rm -rf /src/opengateway/__pycache__ \
    && find /src/opengateway -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

# ── Stage 2: minimal runtime image ───────────────────────────────────────────
# The Python interpreter is the heaviest dep. ``python:3.12-slim`` is the
# smallest image that ships a libpython 3.12 the Mojo runtime can dlopen
# (the Mojo runtime was built against Python 3.12; 3.13+ renamed
# Py_NewRef → _Py_NewRef and breaks the symbol resolution).
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install the Python dependencies the bridge imports at runtime
# (httpx / pydantic / asyncpg / redis / structlog / ...). Done before
# the source copy so the layer caches on pyproject.toml alone.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --only-binary=:all: \
    fastapi "uvicorn[standard]" pydantic pydantic-settings \
    "httpx[http2]" structlog redis asyncpg prometheus-client python-dotenv

COPY --from=builder /src/opengateway /app/opengateway
COPY --from=builder /src/opengateway-mojo /usr/local/bin/opengateway-mojo
# Ship flare's TLS + rustls QUIC FFI cdylibs alongside the binary so
# both the cleartext-on-loopback default and a future HTTP/3 deploy
# have the right libs findable without rebuilding the image.
COPY --from=builder /opt/conda/lib/libflare_tls.so /usr/local/lib/ 2>/dev/null || \
    cp $(find /opt/conda -name libflare_tls.so -print -quit) /usr/local/lib/ 2>/dev/null || \
    echo "libflare_tls.so not found at expected path; image stays smaller"
COPY --from=builder $(find /opt/conda -name libflare_rustls_quic.so -print -quit) /usr/local/lib/ 2>/dev/null || \
    echo "libflare_rustls_quic.so not found; HTTP/3 deploys will need to install it"

# The Mojo binary locates the FFI .so's by canonical name (``libflare_tls``,
# ``libflare_rustls_quic``) and dlopens them lazily; ``/usr/local/lib`` is
# already on the default loader path so no extra LD_LIBRARY_PATH is
# needed. The Python bridge lives in /app/opengateway; the binary
# imports ``opengateway.mojo_bridge`` which transitively imports
# ``opengateway.providers.*`` — so PYTHONPATH must include /app.
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Match the non-root UID the prior image used.
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# The Mojo binary prints "listening on <addr>" then blocks in the
# reactor loop until SIGTERM. SIGINT also works (flare installs a
# graceful drain handler).
ENTRYPOINT ["/usr/local/bin/opengateway-mojo"]
CMD []