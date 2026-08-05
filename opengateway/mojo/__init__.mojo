"""opengateway Mojo package.

Re-exports the Mojo entry point so ``mojo run opengateway/mojo/__init__.mojo``
works as a direct alternative to ``mojo run opengateway/mojo/main.mojo``.
"""
from .main import serve as main