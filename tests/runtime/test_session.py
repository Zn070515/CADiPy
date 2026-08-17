from __future__ import annotations

import threading

import pytest

from cadipy.backends.executor import ApplicationInfo
from cadipy.domain.errors import CadipyError, SessionClosedError
from cadipy.session import CadipySession


class FakeExecutor:
    executor_kind = "fake"

    def __init__(self) -> None:
        self.connected = False
        self.disconnected = False
        self.created_thread_id = threading.get_ident()

    def attach(self, *, visible: bool | None = None) -> ApplicationInfo:
        self.connected = True
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)

    def disconnect(self) -> None:
        self.disconnected = True

    def application_info(self) -> ApplicationInfo:
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)


@pytest.fixture
def session_executor() -> FakeExecutor:
    return FakeExecutor()


def test_session_shares_one_dispatcher_with_rpc_and_mcp(
    session_executor: FakeExecutor,
) -> None:
    executor = session_executor

    with CadipySession(executor=executor, connection_mode="attach") as session:
        assert session.server.session is session
        assert session.mcp.server.session is session
        result = session.execute("application.info")
        assert result.data["executor"] == "fake"

    assert executor.disconnected is True
    with pytest.raises(SessionClosedError):
        session.execute("application.info")


def test_session_constructs_executor_and_dispatcher_on_host_thread() -> None:
    created: list[FakeExecutor] = []
    host_thread_id: list[int] = []

    def factory() -> FakeExecutor:
        created.append(FakeExecutor())
        return created[-1]

    with CadipySession(executor_factory=factory, connection_mode="attach") as session:
        host_thread_id.append(session._host.submit(threading.get_ident))
        result = session.execute("application.info")

    assert created[0].created_thread_id == host_thread_id[0]
    assert result.ok is True


def test_session_exit_disconnects_when_dispatch_raises() -> None:
    executor = FakeExecutor()

    def application_info() -> ApplicationInfo:
        raise CadipyError("application info failed")

    executor.application_info = application_info  # type: ignore[method-assign]

    with (
        pytest.raises(CadipyError, match="application info failed"),
        CadipySession(executor=executor, connection_mode="attach") as session,
    ):
        session.execute("application.info")

    assert executor.disconnected is True
