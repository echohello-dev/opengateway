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
    && pixi run -e mojo mojo build opengateway/mojo/main.mojo \
        -O3 -D ASSERT=none \
        -o /src/opengateway-mojo

# Copy the Python source the binary needs at runtime (provider
# adapters, auth, settings). The bridge imports them by package name.
COPY opengateway/ /src/opengateway/

# Strip the FFI libraries we no longer need in the final image — the
# flare TLS / zlib / brotli FFI is statically linked or unused on the
# chat-completion path; keep ``build/libflare_tls.so`` only if you use
# HTTPS termination. For the default deployment (cleartext HTTP behind
# a TLS-terminating LB) the .so is not required.
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

# The Mojo binary looks for ``build/libflare_tls.so`` relative to the
# working directory at startup. Stage 1 doesn't ship it because the
# default deployment is cleartext HTTP; if you opt into TLS, mount it:
#   docker run -v $(pwd)/build:/app/build ...
# or copy it into the runtime stage above.
#
# The Python bridge lives in /app/opengateway; the binary imports
# ``opengateway.mojo_bridge`` which transitively imports
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