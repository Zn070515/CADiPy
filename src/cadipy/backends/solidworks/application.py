"""Small internal wrapper around the live SOLIDWORKS application object."""

from __future__ import annotations

from typing import Any

from cadipy.domain.errors import ComOperationError, SolidWorksNotAvailableError


def connect_application() -> Any:
    try:
        import win32com.client
    except ImportError as exc:
        raise SolidWorksNotAvailableError(
            "pywin32 is not installed",
            operation="solidworks.connect",
        ) from exc

    try:
        return win32com.client.Dispatch("SldWorks.Application")
    except Exception as exc:
        raise SolidWorksNotAvailableError(
            "SOLIDWORKS COM application is not reachable",
            operation="solidworks.connect",
        ) from exc


def application_info(application: Any, *, executor: str) -> tuple[str, str, str]:
    try:
        revision = str(application.RevisionNumber)
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS revision could not be read",
            operation="solidworks.connect",
        ) from exc
    return "SOLIDWORKS", revision, executor
