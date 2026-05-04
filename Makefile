.PHONY: install dev test lint format run docker-build docker-run clean

install:
	pip install -e "."

dev:
	pip install -e ".[dev]"

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

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
