"""MCP adapter derived from the shared operation registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cadipy.operations.registry import operation_names

if TYPE_CHECKING:
    from .server import ProtocolServer


def exposed_mcp_operations() -> tuple[str, ...]:
    return operation_names()


class McpAdapter:
    def __init__(self, server: ProtocolServer) -> None:
        self.server = server

    def call(
        self, operation: str, params: dict[str, Any], *, request_id: str = "mcp-request"
    ) -> dict[str, Any]:
        return self.server.handle(
            {"protocol": 1, "id": request_id, "operation": operation, "params": params}
        )
