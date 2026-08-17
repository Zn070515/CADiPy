"""Read-only diagnostics for Python, COM, SOLIDWORKS, and executor state."""

from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from cadipy.backends.solidworks import PythonComSolidWorksExecutor
from cadipy.domain.errors import SolidWorksNotAvailableError, UnsupportedVersionError

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class EnvironmentReport:
    python_version: str
    platform: str
    pywin32_available: bool
    com_reachable: bool
    solidworks_revision: str | None
    executor: str | None
    protocol_version: int = 1
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def collect_environment(
    *,
    executor_factory: Callable[[], Any] | None = None,
    strict: bool = False,
    expected_revision: str = "34.3.2",
) -> EnvironmentReport:
    errors: list[str] = []
    pywin32_available = importlib.util.find_spec("win32com") is not None
    com_reachable = False
    revision = None
    executor_kind = None
    executor = (executor_factory or PythonComSolidWorksExecutor)()
    try:
        info = executor.connect()
        com_reachable = True
        revision = info.revision
        executor_kind = info.executor
    except Exception as exc:
        errors.append(type(exc).__name__)
    finally:
        disconnect = getattr(executor, "disconnect", None)
        if callable(disconnect):
            disconnect()
    report = EnvironmentReport(
        python_version=platform.python_version() or sys.version.split()[0],
        platform=platform.platform(),
        pywin32_available=pywin32_available,
        com_reachable=com_reachable,
        solidworks_revision=revision,
        executor=executor_kind,
        errors=tuple(errors),
    )
    if strict and not report.com_reachable:
        raise SolidWorksNotAvailableError(
            "strict SolidWorks diagnostics could not reach COM",
            operation="diagnostics.environment",
            details={"errors": report.errors},
        )
    if strict and report.solidworks_revision != expected_revision:
        raise UnsupportedVersionError(
            "strict SolidWorks diagnostics observed an unsupported revision",
            operation="diagnostics.environment",
            details={
                "expected_revision": expected_revision,
                "observed_revision": report.solidworks_revision,
            },
        )
    return report
