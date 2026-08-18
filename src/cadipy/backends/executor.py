"""Backend-neutral execution port and serializable result values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from cadipy.domain.documents import DocumentType

if TYPE_CHECKING:
    from pathlib import Path

    from cadipy.domain.sketches import (
        DimensionHandle,
        DimensionInspection,
        DimensionType,
        RelationHandle,
        RelationType,
        SketchEntityHandle,
        SketchEntityInspection,
        SketchInspection,
    )
    from cadipy.runtime.mutation import MutationSnapshot


@dataclass(frozen=True, slots=True)
class ApplicationInfo:
    product: str
    revision: str
    executor: str
    connection_mode: str = "attach"
    owned: bool = False
    visible: bool = False


@dataclass(frozen=True, slots=True)
class DocumentHandle:
    id: str
    document_type: DocumentType
    title: str
    path: Path | None = None
    configuration: str | None = None
    active: bool = False

    kind = "document"


@dataclass(frozen=True, slots=True)
class SketchHandle:
    id: str
    document_id: str
    name: str
    plane: str
    persistent_ref: str | None = None

    kind = "sketch"


@dataclass(frozen=True, slots=True)
class GeometryHandle:
    id: str
    sketch_id: str
    width_mm: float
    height_mm: float

    kind = "geometry"


@dataclass(frozen=True, slots=True)
class FeatureHandle:
    id: str
    document_id: str
    name: str
    feature_type: str
    depth_mm: float

    kind = "feature"


@dataclass(frozen=True, slots=True)
class RebuildReport:
    success: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SaveReport:
    success: bool
    path: Path
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentInspection:
    document_id: str
    document_type: DocumentType
    path: Path | None
    title: str
    sketch_names: tuple[str, ...] = ()
    feature_names: tuple[str, ...] = ()
    bounding_box_mm: tuple[float, float, float, float, float, float] | None = None
    body_count: int | None = None
    rectangle_width_mm: float | None = None
    rectangle_height_mm: float | None = None
    extrusion_depth_mm: float | None = None
    feature_suppressed: bool | None = None
    rebuild_success: bool | None = None


@runtime_checkable
class SolidWorksExecutor(Protocol):
    """Stable semantic port implemented by Python COM and future C# workers."""

    executor_kind: str

    def attach(self, *, visible: bool | None = None) -> ApplicationInfo: ...

    def launch(self, *, visible: bool = True) -> ApplicationInfo: ...

    def connect(self) -> ApplicationInfo: ...

    def set_visibility(self, visible: bool) -> ApplicationInfo: ...

    def application_info(self) -> ApplicationInfo: ...

    def disconnect(self) -> None: ...

    def list_documents(self) -> tuple[DocumentHandle, ...]: ...

    def active_document(self) -> DocumentHandle | None: ...

    def open_document(
        self,
        path: Path,
        document_type: DocumentType = DocumentType.PART,
    ) -> DocumentHandle: ...

    def create_part(self) -> DocumentHandle: ...

    def create_sketch(self, document: DocumentHandle, plane: str) -> SketchHandle: ...

    def list_sketches(self, document: DocumentHandle) -> tuple[SketchHandle, ...]: ...

    def inspect_sketch(
        self, document: DocumentHandle, sketch: SketchHandle
    ) -> SketchInspection: ...

    def add_line(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        start_x_mm: float,
        start_y_mm: float,
        end_x_mm: float,
        end_y_mm: float,
    ) -> SketchEntityHandle: ...

    def add_sketch_rectangle(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        width_mm: float,
        height_mm: float,
        origin_x_mm: float = 0.0,
        origin_y_mm: float = 0.0,
    ) -> tuple[SketchEntityHandle, ...]: ...

    def add_circle(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        center_x_mm: float,
        center_y_mm: float,
        radius_mm: float,
    ) -> SketchEntityHandle: ...

    def add_arc(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        center_x_mm: float,
        center_y_mm: float,
        start_x_mm: float,
        start_y_mm: float,
        end_x_mm: float,
        end_y_mm: float,
        direction: int = 1,
    ) -> SketchEntityHandle: ...

    def add_relation(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        relation_type: RelationType,
        entities: tuple[SketchEntityHandle, ...],
        anchor_origin: bool = False,
    ) -> RelationHandle: ...

    def add_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension_type: DimensionType,
        entities: tuple[SketchEntityHandle, ...],
        value_mm: float,
        position_x_mm: float,
        position_y_mm: float,
    ) -> DimensionHandle: ...

    def set_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension: DimensionHandle,
        value_mm: float,
    ) -> DimensionHandle: ...

    def inspect_entity(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        entity: SketchEntityHandle,
    ) -> SketchEntityInspection: ...

    def inspect_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension: DimensionHandle,
    ) -> DimensionInspection: ...

    def add_rectangle(
        self,
        sketch: SketchHandle,
        width_mm: float,
        height_mm: float,
    ) -> GeometryHandle: ...

    def extrude(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        depth_mm: float,
    ) -> FeatureHandle: ...

    def rebuild(self, document: DocumentHandle) -> RebuildReport: ...

    def save(self, document: DocumentHandle, path: Path) -> SaveReport: ...

    def close(self, document: DocumentHandle) -> None: ...

    def reopen(self, path: Path) -> DocumentHandle: ...

    def inspect_document(self, document: DocumentHandle) -> DocumentInspection: ...

    def begin_mutation(self, snapshot: MutationSnapshot) -> None: ...

    def commit_mutation(self, snapshot: MutationSnapshot) -> None: ...

    def rollback_mutation(self, snapshot: MutationSnapshot) -> None: ...

    def verify_rollback(self, snapshot: MutationSnapshot) -> bool: ...

    def record_created_resource(self, resource_id: str) -> None: ...
