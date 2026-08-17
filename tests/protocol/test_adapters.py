from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from cadipy.protocol.client import ProtocolClient
from cadipy.protocol.mcp import McpAdapter
from cadipy.protocol.server import ProtocolServer
from cadipy.session import CadipySession


def test_rpc_and_mcp_adapters_share_dispatcher_and_serialized_result() -> None:
    server = ProtocolServer.from_executor(_FakeExecutor())
    request = {
        "protocol": 1,
        "id": "request-1",
        "operation": "diagnostics.connect",
        "params": {},
    }
    rpc_result = server.handle(request)
    client_result = ProtocolClient(server.handle).call(request)
    mcp_result = McpAdapter(server).call("diagnostics.connect", {})

    assert rpc_result == client_result
    assert rpc_result["operation"] == mcp_result["operation"]
    assert rpc_result["ok"] is True
    assert rpc_result["data"] == mcp_result["data"]
    assert rpc_result["data"]["executor"] == "fake"


def test_protocol_failure_uses_additive_execution_result_field() -> None:
    server = ProtocolServer.from_executor(_FakeExecutor())

    result = server.handle(
        {
            "protocol": 99,
            "id": "request-2",
            "operation": "diagnostics.connect",
        }
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "protocol"
    assert result["execution"] is None


def test_session_adapters_route_concurrent_requests_through_one_host_thread() -> None:
    executor = _RecordingExecutor()
    with CadipySession(executor=executor) as session:
        server = ProtocolServer.from_session(session)
        requests = [
            {
                "protocol": 1,
                "id": f"request-{index}",
                "operation": "diagnostics.connect",
                "params": {},
            }
            for index in range(8)
        ]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(server.handle, requests))

    assert all(result["ok"] for result in results)
    assert len(set(executor.thread_ids)) == 1
    assert executor.request_ids == [request["id"] for request in requests]
    assert not hasattr(server, "dispatcher")
    assert not hasattr(McpAdapter(server), "dispatcher")


class _FakeExecutor:
    executor_kind = "fake"

    def connect(self):
        from cadipy.backends.executor import ApplicationInfo

        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)


class _RecordingExecutor(_FakeExecutor):
    def __init__(self) -> None:
        self.thread_ids: list[int] = []
        self.request_ids: list[str] = []
        self.disconnected = False

    def disconnect(self):
        self.disconnected = True

    def attach(self, *, visible=None):
        return self._record("attach", visible)

    def connect(self):
        return self._record("connect", None)

    def _record(self, operation: str, visible):
        self.thread_ids.append(threading.get_ident())
        if operation == "connect":
            self.request_ids.append("request-" + str(len(self.request_ids)))
        from cadipy.backends.executor import ApplicationInfo

        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)
