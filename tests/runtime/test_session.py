from __future__ import annotations

import pytest

from cadipy.backends.executor import ApplicationInfo
from cadipy.domain.errors import SessionClosedError
from cadipy.session import CadipySession


class FakeExecutor:
    executor_kind = "fake"

    def __init__(self) -> None:
        self.connected = False
        self.disconnected = False

    def attach(self) -> ApplicationInfo:
        self.connected = True
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)

    def disconnect(self) -> None:
        self.disconnected = True

    def application_info(self) -> ApplicationInfo:
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)


def test_session_shares_one_dispatcher_with_rpc_and_mcp() -> None:
    executor = FakeExecutor()

    with CadipySession(executor=executor, connection_mode="attach") as session:
        assert session.server.dispatcher is session.dispatcher
        assert session.mcp.server.dispatcher is session.dispatcher
        result = session.execute("application.info")
        assert result.data["executor"] == "fake"

    assert executor.disconnected is True
    with pytest.raises(SessionClosedError):
        session.execute("application.info")
