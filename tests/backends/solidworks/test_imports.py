from __future__ import annotations

import sys


def test_solidworks_backend_imports_without_eager_com_import() -> None:
    import cadipy.backends.solidworks as solidworks

    assert hasattr(solidworks, "PythonComSolidWorksExecutor")
    assert "win32com.client" not in sys.modules
