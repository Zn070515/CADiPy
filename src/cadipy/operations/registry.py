"""The single source of truth for CADiPy operation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from .schema import ParamSpec, ParamType, PostconditionSpec


@dataclass(frozen=True, slots=True)
class OpSpec:
    name: str
    description: str
    mutating: bool
    target_required: bool
    target_document_types: tuple[str, ...]
    result_document_types: tuple[str, ...]
    parameters: Mapping[str, ParamSpec]
    postconditions: tuple[PostconditionSpec, ...] = ()

    @property
    def parameter_names(self) -> tuple[str, ...]:
        return tuple(sorted(self.parameters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mutating": self.mutating,
            "target_required": self.target_required,
            "target_document_types": list(self.target_document_types),
            "result_document_types": list(self.result_document_types),
            "parameters": {name: value.to_dict() for name, value in self.parameters.items()},
            "postconditions": [value.to_dict() for value in self.postconditions],
        }


OPERATION_REGISTRY: dict[str, OpSpec] = {
    "application.attach": OpSpec(
        name="application.attach",
        description="Attach to an already-running SOLIDWORKS application.",
        mutating=False,
        target_required=False,
        parameters={},
        target_document_types=(),
        result_document_types=(),
    ),
    "application.launch": OpSpec(
        name="application.launch",
        description="Launch a new owned SOLIDWORKS application instance.",
        mutating=True,
        target_required=False,
        parameters={"visible": ParamSpec(type=ParamType.BOOLEAN, default=True)},
        postconditions=(PostconditionSpec(name="application.visible == visible"),),
        target_document_types=(),
        result_document_types=(),
    ),
    "application.set_visibility": OpSpec(
        name="application.set_visibility",
        description="Set the visibility of the connected SOLIDWORKS application.",
        mutating=True,
        target_required=False,
        parameters={"visible": ParamSpec(type=ParamType.BOOLEAN, required=True)},
        postconditions=(PostconditionSpec(name="application.visible == visible"),),
        target_document_types=(),
        result_document_types=(),
    ),
    "application.info": OpSpec(
        name="application.info",
        description="Report the connected SOLIDWORKS application.",
        mutating=False,
        target_required=False,
        parameters={},
        target_document_types=(),
        result_document_types=(),
    ),
    "diagnostics.connect": OpSpec(
        name="diagnostics.connect",
        description="Report the connected SOLIDWORKS execution backend.",
        mutating=False,
        target_required=False,
        parameters={},
        target_document_types=(),
        result_document_types=(),
    ),
    "document.create_part": OpSpec(
        name="document.create_part",
        description="Create a new SOLIDWORKS Part document.",
        mutating=True,
        target_required=False,
        parameters={},
        target_document_types=(),
        result_document_types=("part",),
    ),
    "document.list": OpSpec(
        name="document.list",
        description="List documents currently open in SOLIDWORKS.",
        mutating=False,
        target_required=False,
        parameters={},
        target_document_types=(),
        result_document_types=(),
    ),
    "document.active": OpSpec(
        name="document.active",
        description="Report the currently active SOLIDWORKS document.",
        mutating=False,
        target_required=False,
        parameters={},
        target_document_types=(),
        result_document_types=(),
    ),
    "document.open": OpSpec(
        name="document.open",
        description="Open and register a SOLIDWORKS Part document by path.",
        mutating=True,
        target_required=False,
        parameters={
            "document_type": ParamSpec(type=ParamType.STRING, required=False, default="part"),
            "path": ParamSpec(type=ParamType.PATH, required=True),
        },
        target_document_types=(),
        result_document_types=("part",),
    ),
    "document.close": OpSpec(
        name="document.close",
        description="Close one explicitly bound SOLIDWORKS document.",
        mutating=True,
        target_required=True,
        parameters={},
        target_document_types=("part", "assembly", "drawing"),
        result_document_types=(),
    ),
    "document.inspect": OpSpec(
        name="document.inspect",
        description="Inspect a bound document without changing it.",
        mutating=False,
        target_required=True,
        parameters={},
        target_document_types=("part", "assembly", "drawing"),
        result_document_types=(),
    ),
    "sketch.create": OpSpec(
        name="sketch.create",
        description="Create a sketch on a named Part reference plane.",
        mutating=True,
        target_required=True,
        parameters={"plane": ParamSpec(type=ParamType.STRING, required=True)},
        postconditions=(PostconditionSpec(name="sketch_exists"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.list": OpSpec(
        name="sketch.list",
        description="List sketches in a bound Part document.",
        mutating=False,
        target_required=True,
        parameters={},
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.inspect": OpSpec(
        name="sketch.inspect",
        description="Inspect a specific sketch and its solver state.",
        mutating=False,
        target_required=True,
        parameters={"sketch": ParamSpec(type=ParamType.OBJECT, required=True)},
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.add_line": OpSpec(
        name="sketch.add_line",
        description="Add one line to a bound sketch using millimetre coordinates.",
        mutating=True,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "start_x_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "start_y_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "end_x_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "end_y_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
        },
        postconditions=(PostconditionSpec(name="entity_exists"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.add_rectangle": OpSpec(
        name="sketch.add_rectangle",
        description="Add four independent lines forming a rectangle in millimetres.",
        mutating=True,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "width_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "height_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "origin_x_mm": ParamSpec(type=ParamType.NUMBER, required=False, default=0.0, unit="mm"),
            "origin_y_mm": ParamSpec(type=ParamType.NUMBER, required=False, default=0.0, unit="mm"),
        },
        postconditions=(PostconditionSpec(name="four_entities_exist"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.add_circle": OpSpec(
        name="sketch.add_circle",
        description="Add a circle to a bound sketch using millimetre coordinates.",
        mutating=True,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "center_x_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "center_y_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "radius_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
        },
        postconditions=(PostconditionSpec(name="entity_exists"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.add_arc": OpSpec(
        name="sketch.add_arc",
        description="Add a center-defined arc to a bound sketch.",
        mutating=True,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "center_x_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "center_y_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "start_x_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "start_y_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "end_x_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "end_y_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "direction": ParamSpec(type=ParamType.INTEGER, required=False, default=1),
        },
        postconditions=(PostconditionSpec(name="entity_exists"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.add_relation": OpSpec(
        name="sketch.add_relation",
        description="Add a named relation to resolved sketch entities.",
        mutating=True,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "relation_type": ParamSpec(type=ParamType.STRING, required=True),
            "entities": ParamSpec(type=ParamType.ARRAY, required=True),
            "anchor_origin": ParamSpec(type=ParamType.BOOLEAN, required=False, default=False),
        },
        postconditions=(PostconditionSpec(name="relation_exists"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.add_dimension": OpSpec(
        name="sketch.add_dimension",
        description="Add a millimetre dimension to resolved sketch entities.",
        mutating=True,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "dimension_type": ParamSpec(type=ParamType.STRING, required=True),
            "entities": ParamSpec(type=ParamType.ARRAY, required=True),
            "value_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "position_x_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "position_y_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
        },
        postconditions=(PostconditionSpec(name="dimension_exists"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.set_dimension": OpSpec(
        name="sketch.set_dimension",
        description="Set an existing sketch dimension in millimetres.",
        mutating=True,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "dimension": ParamSpec(type=ParamType.OBJECT, required=True),
            "value_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
        },
        postconditions=(PostconditionSpec(name="dimension_value_matches"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.inspect_entity": OpSpec(
        name="sketch.inspect_entity",
        description="Inspect one sketch entity after persistent resolution.",
        mutating=False,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "entity": ParamSpec(type=ParamType.OBJECT, required=True),
        },
        target_document_types=("part",),
        result_document_types=(),
    ),
    "sketch.inspect_dimension": OpSpec(
        name="sketch.inspect_dimension",
        description="Inspect one sketch dimension after persistent resolution.",
        mutating=False,
        target_required=True,
        parameters={
            "sketch": ParamSpec(type=ParamType.OBJECT, required=True),
            "dimension": ParamSpec(type=ParamType.OBJECT, required=True),
        },
        target_document_types=("part",),
        result_document_types=(),
    ),
    "part.create_rectangular_extrude": OpSpec(
        name="part.create_rectangular_extrude",
        description="Create and verify a rectangular Part extrusion sequence.",
        mutating=True,
        target_required=False,
        parameters={
            "depth_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "height_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
            "plane": ParamSpec(type=ParamType.STRING, required=False, default="Front Plane"),
            "save_path": ParamSpec(type=ParamType.PATH, required=False),
            "width_mm": ParamSpec(type=ParamType.NUMBER, required=True, unit="mm"),
        },
        postconditions=(
            PostconditionSpec(name="document_is_part"),
            PostconditionSpec(name="rebuild_succeeded"),
            PostconditionSpec(name="feature_exists"),
        ),
        target_document_types=(),
        result_document_types=("part",),
    ),
    "part.rebuild": OpSpec(
        name="part.rebuild",
        description="Rebuild a bound Part and report the rebuild state.",
        mutating=True,
        target_required=True,
        parameters={},
        postconditions=(PostconditionSpec(name="rebuild_succeeded"),),
        target_document_types=("part",),
        result_document_types=(),
    ),
}


def operation_names() -> tuple[str, ...]:
    return tuple(OPERATION_REGISTRY)


def get_operation(name: str) -> OpSpec:
    return OPERATION_REGISTRY[name]
