"""CADiPy public package.

The package root intentionally imports no COM or platform-specific modules.
"""

__version__ = "0.1.0"

from .api import connect, execute, launch
from .session import CadipySession

__all__ = ["CadipySession", "__version__", "connect", "execute", "launch"]
