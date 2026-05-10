# Contributing to OpenGateway

Thank you for considering contributing to OpenGateway. This project is MIT-licensed and all contributions are welcome.

## Getting Started

```bash
# Clone the repository
git clone https://github.com/echohello-dev/opengateway.git
cd opengateway

# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
ruff format .
mypy opengateway/

# Start the gateway
opengateway
```

## Code Style

- Python 3.11+ with type hints
- Formatting with `ruff`
- Type checking with `mypy`
- Maximum line length: 100 characters

## Pull Request Process

1. Ensure your code passes all tests and linting
2. Update documentation if needed
3. Open a pull request with a clear description
