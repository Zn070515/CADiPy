from __future__ import annotations

from cadipy.operations.registry import OPERATION_REGISTRY, operation_names
from cadipy.protocol.mcp import exposed_mcp_operations
from cadipy.protocol.server import exposed_rpc_operations


def test_registry_has_unique_explicit_cad_operation_specs() -> None:
    specs = tuple(OPERATION_REGISTRY.values())
    assert specs
    assert len(operation_names()) == len(specs)
    assert all(spec.name == name for name, spec in OPERATION_REGISTRY.items())
    assert all(spec.parameter_names == tuple(sorted(spec.parameter_names)) for spec in specs)
    assert all(
        not name.endswith("_mm") or "unit" in spec.parameters[name]
        for spec in specs
        for name in spec.parameter_names
    )


def test_rpc_and_mcp_exposure_are_derived_from_the_same_registry() -> None:
    assert exposed_rpc_operations() == operation_names()
    assert exposed_mcp_operations() == operation_names()
