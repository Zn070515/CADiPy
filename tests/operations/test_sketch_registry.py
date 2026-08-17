from __future__ import annotations

from cadipy.operations.registry import OPERATION_REGISTRY


def test_parametric_sketch_operations_are_authoritative_specs() -> None:
    expected = {
        "sketch.create",
        "sketch.list",
        "sketch.inspect",
        "sketch.add_line",
        "sketch.add_rectangle",
        "sketch.add_circle",
        "sketch.add_arc",
        "sketch.add_relation",
        "sketch.add_dimension",
        "sketch.set_dimension",
        "sketch.inspect_entity",
        "sketch.inspect_dimension",
    }

    assert expected <= OPERATION_REGISTRY.keys()
    assert OPERATION_REGISTRY["sketch.add_line"].parameters["start_x_mm"]["unit"] == "mm"
    assert OPERATION_REGISTRY["sketch.add_dimension"].parameters["value_mm"]["unit"] == "mm"
    assert OPERATION_REGISTRY["sketch.add_relation"].parameters["anchor_origin"]["default"] is False
