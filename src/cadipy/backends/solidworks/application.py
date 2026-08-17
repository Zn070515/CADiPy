"""Small internal wrapper around the live SOLIDWORKS application object."""

from __future__ import annotations

from typing import Any

from cadipy.domain.errors import ComOperationError, SolidWorksNotAvailableError


def attach_application() -> Any:
    try:
        import win32com.client
    except ImportError as exc:
        raise SolidWorksNotAvailableError(
            "pywin32 is not installed",
            operation="solidworks.attach",
        ) from exc

    try:
        return win32com.client.GetActiveObject("SldWorks.Application")
    except Exception as exc:
        raise SolidWorksNotAvailableError(
            "no registered SOLIDWORKS application is available to attach",
            operation="solidworks.attach",
        ) from exc


def launch_application() -> Any:
    try:
        import win32com.client
    except ImportError as exc:
        raise SolidWorksNotAvailableError(
            "pywin32 is not installed",
            operation="solidworks.launch",
        ) from exc

    try:
        return win32com.client.DispatchEx("SldWorks.Application")
    except Exception as exc:
        raise SolidWorksNotAvailableError(
            "SOLIDWORKS could not be launched through COM",
            operation="solidworks.launch",
        ) from exc


def exit_application(application: Any) -> None:
    try:
        application.ExitApp()
    except Exception as exc:
        raise ComOperationError(
            "owned SOLIDWORKS application could not be exited",
            operation="solidworks.disconnect",
        ) from exc


def set_visibility(application: Any, visible: bool) -> None:
    try:
        application.Visible = visible
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS application visibility could not be changed",
            operation="solidworks.application.set_visibility",
        ) from exc


def application_info(application: Any, *, executor: str) -> tuple[str, str, str, bool]:
    try:
        revision = str(application.RevisionNumber)
        visible = bool(application.Visible)
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS revision could not be read",
            operation="solidworks.connect",
        ) from exc
    return "SOLIDWORKS", revision, executor, visible
