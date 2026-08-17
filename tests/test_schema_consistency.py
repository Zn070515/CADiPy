from __future__ import annotations

from cadipy.operations.registry import operation_names
from cadipy.protocol.mcp import exposed_mcp_operations
from cadipy.protocol.server import exposed_rpc_operations


def test_all_agent_surfaces_are_registry_operations() -> None:
    registry = set(operation_names())
    assert set(exposed_rpc_operations()) == registry
    assert set(exposed_mcp_operations()) == registry
