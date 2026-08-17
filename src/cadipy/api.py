"""Stable Python-facing API built on the shared operation dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cadipy.operations.dispatch import OperationDispatcher
from cadipy.session import CadipySession, ConnectionMode

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

    if executor is None:
        with connect() as session:
            return session.execute(
                operation,
                params=params,
                target=target,
                request_id=request_id,
            )
    selected = executor
    return OperationDispatcher(selected).dispatch(
        {
            "id": request_id,
            "operation": operation,
            "params": params or {},
            "target": target,
        }
    )


def connect(
    *,
    mode: ConnectionMode = "attach",
    visible: bool | None = None,
    executor: SolidWorksExecutor | None = None,
) -> CadipySession:
    """Create a persistent session; application acquisition occurs on entry."""

    return CadipySession(executor=executor, connection_mode=mode, visible=visible)


def launch(
    *,
    visible: bool = True,
    executor: SolidWorksExecutor | None = None,
) -> CadipySession:
    """Create a persistent session that explicitly owns a new application."""

    return CadipySession(executor=executor, connection_mode="launch", visible=visible)
