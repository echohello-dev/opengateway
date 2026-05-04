# Contributing to OpenGateway

Thank you for considering contributing to OpenGateway. This project is MIT-licensed and all contributions are welcome.

## Developer Certificate of Origin (DCO)

By contributing to this project, you agree to the [Developer Certificate of Origin](https://developercertificate.org/):

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
1 Letterman Drive
Suite D4700
San Francisco, CA, 94129

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

## How to Sign Off

All commits must include a `Signed-off-by:` line. Use the `-s` flag with git:

```bash
git commit -s -m "feat: add new provider adapter"
```

## Getting Started

```bash
# Clone the repository
git clone https://github.com/echohello-dev/opengateway.git
cd opengateway

# Install dependencies
pip install -e ".[dev]"

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
3. Sign your commits with `git commit -s`
4. Open a pull request with a clear description
