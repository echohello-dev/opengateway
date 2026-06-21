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

mojo-install:
	curl -fsSL https://pixi.sh/install.sh | sh

mojo-test:
	pixi run -e mojo mojo run opengateway/mojo/test_router.mojo

mojo-build:
	pixi run -e mojo mojo build opengateway/mojo/main.mojo -O3 -D ASSERT=none -o dist-mojo/opengateway-mojo

mojo-serve:
	pixi run -e mojo mojo run opengateway/mojo/main.mojo

mojo-format:
	pixi run -e mojo mojo format opengateway/mojo/

mojo-fmt-check:
	pixi run -e mojo mojo format --check opengateway/mojo/

clean:
	rm -rf build/ dist/ dist-mojo/ *.egg-info .pytest_cache .mypy_cache .pixi
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
