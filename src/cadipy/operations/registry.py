"""The single source of truth for CADiPy operation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OpSpec:
    name: str
    description: str
    mutating: bool
    target_required: bool
    document_types: tuple[str, ...]
    parameters: dict[str, dict[str, Any]]
    postconditions: tuple[str, ...] = ()

    @property
    def parameter_names(self) -> tuple[str, ...]:
        return tuple(sorted(self.parameters))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mutating": self.mutating,
            "target_required": self.target_required,
            "document_types": list(self.document_types),
            "parameters": self.parameters,
            "postconditions": list(self.postconditions),
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
        parameters={},
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
