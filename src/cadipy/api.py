"""Stable Python-facing API built on the shared operation dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cadipy.session import CadipySession, ConnectionMode

if TYPE_CHECKING:
    from collections.abc import Callable

    from cadipy.backends.executor import SolidWorksExecutor
    from cadipy.protocol.result import OperationResult


def execute(
    operation: str,
    *,
    params: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    executor: Callable[[], SolidWorksExecutor] | None = None,
    request_id: str = "python-api",
) -> OperationResult:
    """Execute one registry operation without exposing backend objects."""

    with connect(executor_factory=executor) as session:
        return session.execute(
            operation,
            params=params,
            target=target,
            request_id=request_id,
        )


def connect(
    *,
    mode: ConnectionMode = "attach",
    visible: bool | None = None,
    executor_factory: Callable[[], SolidWorksExecutor] | None = None,
) -> CadipySession:
    """Create a persistent session; application acquisition occurs on entry."""

    return CadipySession(
        executor_factory=executor_factory,
        connection_mode=mode,
        visible=visible,
    )


def launch(
    *,
    visible: bool = True,
    executor_factory: Callable[[], SolidWorksExecutor] | None = None,
) -> CadipySession:
    """Create a persistent session that explicitly owns a new application."""

    return CadipySession(
        executor_factory=executor_factory,
        connection_mode="launch",
        visible=visible,
    )
