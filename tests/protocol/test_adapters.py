from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from cadipy.audit.recorder import AuditRecorder
from cadipy.protocol.client import ProtocolClient
from cadipy.protocol.mcp import McpAdapter
from cadipy.protocol.server import ProtocolServer
from cadipy.session import CadipySession


def test_rpc_and_mcp_adapters_share_dispatcher_and_serialized_result() -> None:
    audit = AuditRecorder()
    with CadipySession(executor_factory=_FakeExecutor, audit_recorder=audit) as session:
        server = ProtocolServer.from_session(session)
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
    with CadipySession(executor_factory=_FakeExecutor) as session:
        result = session.server.handle(
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
    audit = AuditRecorder()
    with CadipySession(executor_factory=lambda: executor, audit_recorder=audit) as session:
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
        turns = [Event() for _ in requests]
        turns[0].set()

        def call(index: int) -> dict[str, object]:
            assert turns[index].wait(timeout=1.0)
            result = server.handle(requests[index])
            if index + 1 < len(turns):
                turns[index + 1].set()
            return result

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(call, range(len(requests))))

    assert all(result["ok"] for result in results)
    assert len(set(executor.thread_ids)) == 1
    assert [event["request_id"] for event in audit.to_list()] == [
        request["id"] for request in requests
    ]
    assert not hasattr(server, "dispatcher")
    assert not hasattr(McpAdapter(server), "dispatcher")
    assert not hasattr(ProtocolServer, "from_executor")


class _FakeExecutor:
    executor_kind = "fake"

    def attach(self, *, visible=None):
        return self.application_info()

    def disconnect(self):
        return None

    def application_info(self):
        from cadipy.backends.executor import ApplicationInfo

        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)

    def connect(self):
        from cadipy.backends.executor import ApplicationInfo

        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)


class _RecordingExecutor(_FakeExecutor):
    def __init__(self) -> None:
        self.thread_ids: list[int] = []

    def attach(self, *, visible=None):
        self.thread_ids.append(threading.get_ident())
        return self.application_info()

    def connect(self):
        self.thread_ids.append(threading.get_ident())
        return self.application_info()
