from __future__ import annotations

from cadipy.protocol.client import ProtocolClient
from cadipy.protocol.mcp import McpAdapter
from cadipy.protocol.server import ProtocolServer


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


class _FakeExecutor:
    executor_kind = "fake"

    def connect(self):
        from cadipy.backends.executor import ApplicationInfo

        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)
