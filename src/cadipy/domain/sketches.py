"""Serializable CADiPy sketch identity and parameter values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SketchEntityType(str, Enum):
    POINT = "point"
    LINE = "line"
    CIRCLE = "circle"
    ARC = "arc"


class RelationType(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    COINCIDENT = "coincident"
    PARALLEL = "parallel"
    PERPENDICULAR = "perpendicular"
    TANGENT = "tangent"
    CONCENTRIC = "concentric"


class DimensionType(str, Enum):
    DISTANCE = "distance"
    HORIZONTAL_DISTANCE = "horizontal_distance"
    VERTICAL_DISTANCE = "vertical_distance"
    RADIUS = "radius"
    DIAMETER = "diameter"


@dataclass(frozen=True, slots=True)
class SketchEntityHandle:
    id: str
    document_id: str
    sketch_id: str
    entity_type: SketchEntityType
    persistent_ref: str
    sketch_persistent_ref: str | None = None
    start_x_mm: float | None = None
    start_y_mm: float | None = None
    end_x_mm: float | None = None
    end_y_mm: float | None = None
    center_x_mm: float | None = None
    center_y_mm: float | None = None
    radius_mm: float | None = None

    kind = "sketch_entity"


@dataclass(frozen=True, slots=True)
class RelationHandle:
    id: str
    sketch_id: str
    relation_type: RelationType
    entity_ids: tuple[str, ...]

    kind = "sketch_relation"


@dataclass(frozen=True, slots=True)
class DimensionHandle:
    id: str
    sketch_id: str
    dimension_type: DimensionType
    name: str
    value_mm: float
    persistent_ref: str | None = None

    kind = "sketch_dimension"


@dataclass(frozen=True, slots=True)
class SketchInspection:
    sketch_id: str
    name: str
    plane: str
    entity_count: int
    relation_count: int
    dimension_count: int
    fully_defined: bool | None


@dataclass(frozen=True, slots=True)
class SketchEntityInspection:
    handle: SketchEntityHandle
    entity_type: SketchEntityType
    relation_count: int


@dataclass(frozen=True, slots=True)
class DimensionInspection:
    handle: DimensionHandle
    value_mm: float
    driven: bool | None = None
