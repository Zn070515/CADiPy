"""The single source of truth for CADiPy operation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

from .schema import ParamSpec, PostconditionSpec


@dataclass(frozen=True, slots=True)
class OpSpec:
    name: str
    description: str
    mutating: bool
    target_required: bool
    target_document_types: tuple[str, ...] = ()
    result_document_types: tuple[str, ...] = ()
    parameters: Mapping[str, ParamSpec | Mapping[str, Any]] = field(default_factory=dict)
    postconditions: tuple[PostconditionSpec | str, ...] = ()
    document_types: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        legacy_types = self.document_types or ()
        target_types = self.target_document_types
        result_types = self.result_document_types
        if not target_types and self.target_required:
            target_types = legacy_types
        if not result_types and not self.target_required:
            result_types = legacy_types
        object.__setattr__(self, "target_document_types", tuple(target_types))
        object.__setattr__(self, "result_document_types", tuple(result_types))
        object.__setattr__(
            self,
            "parameters",
            {
                name: declaration
                if isinstance(declaration, ParamSpec)
                else ParamSpec(
                    type=declaration["type"],
                    **{key: value for key, value in declaration.items() if key != "type"},
                )
                for name, declaration in dict(self.parameters).items()
            },
        )
        object.__setattr__(
            self,
            "postconditions",
            tuple(
                condition
                if isinstance(condition, PostconditionSpec)
                else PostconditionSpec(name=condition)
                for condition in self.postconditions
            ),
        )

    @property
    def document_types_legacy(self) -> tuple[str, ...]:
        return self.target_document_types or self.result_document_types

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
            "parameters": {
                name: cast("ParamSpec", value).to_dict() for name, value in self.parameters.items()
            },
            "postconditions": [
                cast("PostconditionSpec", value).to_dict() for value in self.postconditions
            ],
        }


OPERATION_REGISTRY: dict[str, OpSpec] = {
    "application.attach": OpSpec(
        name="application.attach",
        description="Attach to an already-running SOLIDWORKS application.",
        mutating=False,
        target_required=False,
        document_types=(),
        parameters={},
    ),
    "application.launch": OpSpec(
        name="application.launch",
        description="Launch a new owned SOLIDWORKS application instance.",
        mutating=True,
        target_required=False,
        document_types=(),
        parameters={
            "visible": {"type": "boolean", "default": True},
        },
        postconditions=("application.visible == visible",),
    ),
    "application.set_visibility": OpSpec(
        name="application.set_visibility",
        description="Set the visibility of the connected SOLIDWORKS application.",
        mutating=True,
        target_required=False,
        document_types=(),
        parameters={
            "visible": {"type": "boolean", "required": True},
        },
        postconditions=("application.visible == visible",),
    ),
    "application.info": OpSpec(
        name="application.info",
        description="Report the connected SOLIDWORKS application.",
        mutating=False,
        target_required=False,
        document_types=(),
        parameters={},
    ),
    "diagnostics.connect": OpSpec(
        name="diagnostics.connect",
        description="Report the connected SOLIDWORKS execution backend.",
        mutating=False,
        target_required=False,
        document_types=(),
        parameters={},
    ),
    "document.create_part": OpSpec(
        name="document.create_part",
        description="Create a new SOLIDWORKS Part document.",
        mutating=True,
        target_required=False,
        document_types=("part",),
        parameters={},
    ),
    "document.list": OpSpec(
        name="document.list",
        description="List documents currently open in SOLIDWORKS.",
        mutating=False,
        target_required=False,
        document_types=(),
        parameters={},
    ),
    "document.active": OpSpec(
        name="document.active",
        description="Report the currently active SOLIDWORKS document.",
        mutating=False,
        target_required=False,
        document_types=(),
        parameters={},
    ),
    "document.open": OpSpec(
        name="document.open",
        description="Open and register a SOLIDWORKS Part document by path.",
        mutating=True,
        target_required=False,
        document_types=("part",),
        parameters={
            "document_type": {
                "type": "string",
                "required": False,
                "default": "part",
            },
            "path": {"type": "path", "required": True},
        },
    ),
    "document.close": OpSpec(
        name="document.close",
        description="Close one explicitly bound SOLIDWORKS document.",
        mutating=True,
        target_required=True,
        document_types=("part", "assembly", "drawing"),
        parameters={},
    ),
    "document.inspect": OpSpec(
        name="document.inspect",
        description="Inspect a bound document without changing it.",
        mutating=False,
        target_required=True,
        document_types=("part", "assembly", "drawing"),
        parameters={},
    ),
    "sketch.create": OpSpec(
        name="sketch.create",
        description="Create a sketch on a named Part reference plane.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={"plane": {"type": "string", "required": True}},
        postconditions=("sketch_exists",),
    ),
    "sketch.list": OpSpec(
        name="sketch.list",
        description="List sketches in a bound Part document.",
        mutating=False,
        target_required=True,
        document_types=("part",),
        parameters={},
    ),
    "sketch.inspect": OpSpec(
        name="sketch.inspect",
        description="Inspect a specific sketch and its solver state.",
        mutating=False,
        target_required=True,
        document_types=("part",),
        parameters={"sketch": {"type": "object", "required": True}},
    ),
    "sketch.add_line": OpSpec(
        name="sketch.add_line",
        description="Add one line to a bound sketch using millimetre coordinates.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "start_x_mm": {"type": "number", "required": True, "unit": "mm"},
            "start_y_mm": {"type": "number", "required": True, "unit": "mm"},
            "end_x_mm": {"type": "number", "required": True, "unit": "mm"},
            "end_y_mm": {"type": "number", "required": True, "unit": "mm"},
        },
        postconditions=("entity_exists",),
    ),
    "sketch.add_rectangle": OpSpec(
        name="sketch.add_rectangle",
        description="Add four independent lines forming a rectangle in millimetres.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "width_mm": {"type": "number", "required": True, "unit": "mm"},
            "height_mm": {"type": "number", "required": True, "unit": "mm"},
            "origin_x_mm": {"type": "number", "required": False, "default": 0.0, "unit": "mm"},
            "origin_y_mm": {"type": "number", "required": False, "default": 0.0, "unit": "mm"},
        },
        postconditions=("four_entities_exist",),
    ),
    "sketch.add_circle": OpSpec(
        name="sketch.add_circle",
        description="Add a circle to a bound sketch using millimetre coordinates.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "center_x_mm": {"type": "number", "required": True, "unit": "mm"},
            "center_y_mm": {"type": "number", "required": True, "unit": "mm"},
            "radius_mm": {"type": "number", "required": True, "unit": "mm"},
        },
        postconditions=("entity_exists",),
    ),
    "sketch.add_arc": OpSpec(
        name="sketch.add_arc",
        description="Add a center-defined arc to a bound sketch.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "center_x_mm": {"type": "number", "required": True, "unit": "mm"},
            "center_y_mm": {"type": "number", "required": True, "unit": "mm"},
            "start_x_mm": {"type": "number", "required": True, "unit": "mm"},
            "start_y_mm": {"type": "number", "required": True, "unit": "mm"},
            "end_x_mm": {"type": "number", "required": True, "unit": "mm"},
            "end_y_mm": {"type": "number", "required": True, "unit": "mm"},
            "direction": {"type": "integer", "required": False, "default": 1},
        },
        postconditions=("entity_exists",),
    ),
    "sketch.add_relation": OpSpec(
        name="sketch.add_relation",
        description="Add a named relation to resolved sketch entities.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "relation_type": {"type": "string", "required": True},
            "entities": {"type": "array", "required": True},
            "anchor_origin": {"type": "boolean", "required": False, "default": False},
        },
        postconditions=("relation_exists",),
    ),
    "sketch.add_dimension": OpSpec(
        name="sketch.add_dimension",
        description="Add a millimetre dimension to resolved sketch entities.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "dimension_type": {"type": "string", "required": True},
            "entities": {"type": "array", "required": True},
            "value_mm": {"type": "number", "required": True, "unit": "mm"},
            "position_x_mm": {"type": "number", "required": True, "unit": "mm"},
            "position_y_mm": {"type": "number", "required": True, "unit": "mm"},
        },
        postconditions=("dimension_exists",),
    ),
    "sketch.set_dimension": OpSpec(
        name="sketch.set_dimension",
        description="Set an existing sketch dimension in millimetres.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "dimension": {"type": "object", "required": True},
            "value_mm": {"type": "number", "required": True, "unit": "mm"},
        },
        postconditions=("dimension_value_matches",),
    ),
    "sketch.inspect_entity": OpSpec(
        name="sketch.inspect_entity",
        description="Inspect one sketch entity after persistent resolution.",
        mutating=False,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "entity": {"type": "object", "required": True},
        },
    ),
    "sketch.inspect_dimension": OpSpec(
        name="sketch.inspect_dimension",
        description="Inspect one sketch dimension after persistent resolution.",
        mutating=False,
        target_required=True,
        document_types=("part",),
        parameters={
            "sketch": {"type": "object", "required": True},
            "dimension": {"type": "object", "required": True},
        },
    ),
    "part.create_rectangular_extrude": OpSpec(
        name="part.create_rectangular_extrude",
        description="Create and verify a rectangular Part extrusion sequence.",
        mutating=True,
        target_required=False,
        document_types=("part",),
        parameters={
            "depth_mm": {"type": "number", "required": True, "unit": "mm"},
            "height_mm": {"type": "number", "required": True, "unit": "mm"},
            "plane": {"type": "string", "required": False, "default": "Front Plane"},
            "save_path": {"type": "path", "required": False},
            "width_mm": {"type": "number", "required": True, "unit": "mm"},
        },
        postconditions=("document_is_part", "rebuild_succeeded", "feature_exists"),
    ),
    "part.rebuild": OpSpec(
        name="part.rebuild",
        description="Rebuild a bound Part and report the rebuild state.",
        mutating=True,
        target_required=True,
        document_types=("part",),
        parameters={},
        postconditions=("rebuild_succeeded",),
    ),
}


def operation_names() -> tuple[str, ...]:
    return tuple(OPERATION_REGISTRY)


def get_operation(name: str) -> OpSpec:
    return OPERATION_REGISTRY[name]
