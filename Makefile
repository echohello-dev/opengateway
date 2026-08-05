.PHONY: install dev test lint format run docker-build docker-run clean mojo-install mojo-test mojo-build mojo-serve mojo-format mojo-fmt-check

install:
	uv pip install -e "."

dev:
	uv pip install -e ".[dev]"

test:
	pytest -v

lint:
	ruff check opengateway/ tests/
	mypy opengateway/

format:
	ruff format opengateway/ tests/

run:
	opengateway

docker-build:
	docker build -t opengateway:latest .

docker-run:
	docker run -p 8080:8080 --env-file .env opengateway:latest

docker-compose-up:
	docker-compose up --build

# ── Mojo (flare) variants ─────────────────────────────────────────────────────

# The Mojo runtime dlopens libpython at startup; point it at the pixi env's
# 3.13 (macOS .dylib / Linux .so) so `Py_NewRef` resolves.
MOJO_PYLIB := $(firstword $(wildcard $(CURDIR)/.pixi/envs/mojo/lib/libpython3.13.dylib $(CURDIR)/.pixi/envs/mojo/lib/libpython3.13.so))

mojo-install:
	curl -fsSL https://pixi.sh/install.sh | sh

mojo-test:
	pixi run -e mojo mojo -I . opengateway/mojo/test_router.mojo

mojo-build:
	pixi run -e mojo mojo build -I . opengateway/mojo/main.mojo -O3 -D ASSERT=none -o dist-mojo/opengateway-mojo

mojo-serve:
	MOJO_PYTHON_LIBRARY=$(MOJO_PYLIB) PYTHONPATH=$(CURDIR) pixi run -e mojo mojo -I . opengateway/mojo/main.mojo

mojo-format:
	pixi run -e mojo mojo format opengateway/mojo/

mojo-fmt-check:
	pixi run -e mojo mojo format --check opengateway/mojo/

clean:
	rm -rf build/ dist/ dist-mojo/ *.egg-info .pytest_cache .mypy_cache .pixi
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
