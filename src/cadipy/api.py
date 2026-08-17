"""Stable Python-facing API built on the shared operation dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cadipy.backends.solidworks import PythonComSolidWorksExecutor
from cadipy.operations.dispatch import OperationDispatcher

if TYPE_CHECKING:
    from cadipy.backends.executor import SolidWorksExecutor
    from cadipy.protocol.result import OperationResult


def execute(
    operation: str,
    *,
    params: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    executor: SolidWorksExecutor | None = None,
    request_id: str = "python-api",
) -> OperationResult:
    """Execute one registry operation without exposing backend objects."""

    owned_executor = executor is None
    selected = executor or PythonComSolidWorksExecutor()
    try:
        if isinstance(selected, PythonComSolidWorksExecutor):
            selected.connect()
        return OperationDispatcher(selected).dispatch(
            {
                "id": request_id,
                "operation": operation,
                "params": params or {},
                "target": target,
            }
        )
    finally:
        if owned_executor and isinstance(selected, PythonComSolidWorksExecutor):
            selected.disconnect()
