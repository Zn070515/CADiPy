"""COM apartment ownership for the SolidWorks backend."""

from __future__ import annotations

from typing import Any

from cadipy.domain.errors import ComOperationError


class ComApartment:
    """Own one COM apartment on the thread that drives the executor."""

    def __init__(self) -> None:
        self._pythoncom: Any = None
        self._entered = False

    def __enter__(self) -> Any:
        try:
            import pythoncom
        except ImportError as exc:
            raise ComOperationError(
                "pywin32 is required for the SolidWorks COM backend",
                operation="solidworks.com.initialize",
            ) from exc

        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        except Exception as exc:
            raise ComOperationError(
                "failed to initialize the SolidWorks COM apartment",
                operation="solidworks.com.initialize",
            ) from exc
        self._pythoncom = pythoncom
        self._entered = True
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._entered and self._pythoncom is not None:
            self._pythoncom.CoUninitialize()
        self._entered = False
        self._pythoncom = None
