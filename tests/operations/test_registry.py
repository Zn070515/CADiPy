from __future__ import annotations

import json

from cadipy.operations.registry import OPERATION_REGISTRY, OpSpec, operation_names
from cadipy.operations.schema import ParamSpec, ParamType, PostconditionSpec
from cadipy.protocol.mcp import exposed_mcp_operations
from cadipy.protocol.server import exposed_rpc_operations


def test_registry_has_unique_explicit_cad_operation_specs() -> None:
    specs = tuple(OPERATION_REGISTRY.values())
    assert specs
    assert len(operation_names()) == len(specs)
    assert all(spec.name == name for name, spec in OPERATION_REGISTRY.items())
    assert all(spec.parameter_names == tuple(sorted(spec.parameter_names)) for spec in specs)
    assert all(
        not name.endswith("_mm") or spec.parameters[name].unit is not None
        for spec in specs
        for name in spec.parameter_names
    )
    assert all(
        isinstance(parameter, ParamSpec) for spec in specs for parameter in spec.parameters.values()
    )
    assert all(
        isinstance(postcondition, PostconditionSpec)
        for spec in specs
        for postcondition in spec.postconditions
    )


def test_operation_spec_exposes_typed_document_and_postcondition_contracts() -> None:
    spec = OpSpec(
        name="part.test",
        description="test",
        mutating=False,
        target_required=True,
        target_document_types=("part",),
        result_document_types=("part",),
        parameters={"depth_mm": ParamSpec(type=ParamType.NUMBER, unit="mm")},
        postconditions=(PostconditionSpec(name="feature_exists"),),
    )

    assert spec.parameters["depth_mm"].type is ParamType.NUMBER
    assert json.loads(json.dumps(spec.to_dict()))["parameters"]["depth_mm"]["type"] == "number"


def test_rpc_and_mcp_exposure_are_derived_from_the_same_registry() -> None:
    assert exposed_rpc_operations() == operation_names()
    assert exposed_mcp_operations() == operation_names()
