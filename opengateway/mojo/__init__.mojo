"""opengateway Mojo package.

Exposes the Mojo HTTP server, router, and auth components built on flare.
The provider adapters live in Python (opengateway.providers) and are
called via Mojo's PythonObject bridge.
"""
from .main import main as serve
