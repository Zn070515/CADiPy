from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from cadipy.backends.executor import (
    ApplicationInfo,
    DocumentHandle,
    DocumentInspection,
    FeatureHandle,
    GeometryHandle,
    RebuildReport,
    SaveReport,
    SketchHandle,
    SolidWorksExecutor,
)
from cadipy.domain.documents import DocumentType
from cadipy.domain.sketches import (
    DimensionHandle,
    DimensionInspection,
    DimensionType,
    RelationHandle,
    RelationType,
    SketchEntityHandle,
    SketchEntityInspection,
    SketchEntityType,
    SketchInspection,
)


class FakeWorkerExecutor:
    """A serializable future-worker-shaped implementation of the port."""

    executor_kind = "csharp-worker"

    def attach(self, *, visible: bool | None = None) -> ApplicationInfo:
        return ApplicationInfo(
            product="SOLIDWORKS",
            revision="34.3.2",
            executor=self.executor_kind,
            connection_mode="attach",
            owned=False,
        )

    def launch(self, *, visible: bool = True) -> ApplicationInfo:
        return ApplicationInfo(
            product="SOLIDWORKS",
            revision="34.3.2",
            executor=self.executor_kind,
            connection_mode="launch",
            owned=True,
        )

    def connect(self) -> ApplicationInfo:
        return self.attach()

    def set_visibility(self, visible: bool) -> ApplicationInfo:
        return ApplicationInfo(
            product="SOLIDWORKS",
            revision="34.3.2",
            executor=self.executor_kind,
            connection_mode="attach",
            owned=False,
            visible=visible,
        )

    def application_info(self) -> ApplicationInfo:
        return self.attach()

    def disconnect(self) -> None:
        return None

    def list_documents(self) -> tuple[DocumentHandle, ...]:
        return ()

    def active_document(self) -> DocumentHandle | None:
        return None

    def open_document(
        self,
        path: Path,
        document_type: DocumentType = DocumentType.PART,
    ) -> DocumentHandle:
        return DocumentHandle(
            id="part-opened",
            document_type=document_type,
            path=path,
            title=path.stem,
        )

    def create_part(self) -> DocumentHandle:
        return DocumentHandle(id="part-1", document_type=DocumentType.PART, title="Part1")

    def create_sketch(self, document: DocumentHandle, plane: str) -> SketchHandle:
        return SketchHandle(id="sketch-1", document_id=document.id, name="Sketch1", plane=plane)

    def list_sketches(self, document: DocumentHandle) -> tuple[SketchHandle, ...]:
        return (self.create_sketch(document, "Front Plane"),)

    def inspect_sketch(self, document: DocumentHandle, sketch: SketchHandle) -> SketchInspection:
        return SketchInspection(sketch.id, sketch.name, sketch.plane, 0, 0, 0, None)

    def add_line(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        start_x_mm: float,
        start_y_mm: float,
        end_x_mm: float,
        end_y_mm: float,
    ) -> SketchEntityHandle:
        return SketchEntityHandle(
            "entity-1",
            document.id,
            sketch.id,
            SketchEntityType.LINE,
            "AQID",
            start_x_mm,
            start_y_mm,
            end_x_mm,
            end_y_mm,
        )

    def add_sketch_rectangle(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        width_mm: float,
        height_mm: float,
        origin_x_mm: float = 0.0,
        origin_y_mm: float = 0.0,
    ) -> tuple[SketchEntityHandle, ...]:
        return (self.add_line(document, sketch, 0, 0, width_mm, height_mm),)

    def add_circle(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        center_x_mm: float,
        center_y_mm: float,
        radius_mm: float,
    ) -> SketchEntityHandle:
        return SketchEntityHandle(
            "circle-1", document.id, sketch.id, SketchEntityType.CIRCLE, "AQID"
        )

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
    ) -> SketchEntityHandle:
        return SketchEntityHandle("arc-1", document.id, sketch.id, SketchEntityType.ARC, "AQID")

    def add_relation(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        relation_type: RelationType,
        entities: tuple[SketchEntityHandle, ...],
    ) -> RelationHandle:
        return RelationHandle("relation-1", sketch.id, relation_type, tuple(e.id for e in entities))

    def add_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension_type: DimensionType,
        entities: tuple[SketchEntityHandle, ...],
        value_mm: float,
        position_x_mm: float,
        position_y_mm: float,
    ) -> DimensionHandle:
        return DimensionHandle("dimension-1", sketch.id, dimension_type, "D1@Sketch1", value_mm)

    def set_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension: DimensionHandle,
        value_mm: float,
    ) -> DimensionHandle:
        return DimensionHandle(
            dimension.id, dimension.sketch_id, dimension.dimension_type, dimension.name, value_mm
        )

    def inspect_entity(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        entity: SketchEntityHandle,
    ) -> SketchEntityInspection:
        return SketchEntityInspection(entity, entity.entity_type, 0)

    def inspect_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension: DimensionHandle,
    ) -> DimensionInspection:
        return DimensionInspection(dimension, dimension.value_mm)

    def add_rectangle(
        self,
        sketch: SketchHandle,
        width_mm: float,
        height_mm: float,
    ) -> GeometryHandle:
        return GeometryHandle(
            id="rectangle-1",
            sketch_id=sketch.id,
            width_mm=width_mm,
            height_mm=height_mm,
        )

    def extrude(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        depth_mm: float,
    ) -> FeatureHandle:
        return FeatureHandle(
            id="feature-1",
            document_id=document.id,
            name="Boss-Extrude1",
            feature_type="extrusion",
            depth_mm=depth_mm,
        )

    def rebuild(self, document: DocumentHandle) -> RebuildReport:
        return RebuildReport(success=True)

    def save(self, document: DocumentHandle, path: Path) -> SaveReport:
        return SaveReport(success=True, path=path)

    def close(self, document: DocumentHandle) -> None:
        return None

    def reopen(self, path: Path) -> DocumentHandle:
        return DocumentHandle(
            id="part-2",
            document_type=DocumentType.PART,
            path=path,
            title=path.stem,
        )

    def inspect_document(self, document: DocumentHandle) -> DocumentInspection:
        return DocumentInspection(
            document_id=document.id,
            document_type=document.document_type,
            path=document.path,
            title=document.title,
            sketch_names=("Sketch1",),
            feature_names=("Boss-Extrude1",),
            bounding_box_mm=(0.0, 0.0, 0.0, 100.0, 60.0, 3.0),
            body_count=1,
        )


def test_future_worker_shape_satisfies_executor_port() -> None:
    executor = FakeWorkerExecutor()
    assert isinstance(executor, SolidWorksExecutor)
    assert executor.connect().executor == "csharp-worker"


def test_executor_port_exposes_explicit_lifecycle_and_document_discovery() -> None:
    executor = FakeWorkerExecutor()

    assert executor.attach().connection_mode == "attach"
    assert executor.launch().connection_mode == "launch"
    assert executor.application_info().executor == "csharp-worker"
    assert executor.list_documents() == ()
    assert executor.active_document() is None


def test_executor_results_are_domain_values_without_com_objects() -> None:
    executor = FakeWorkerExecutor()
    document = executor.create_part()
    sketch = executor.create_sketch(document, "Front Plane")
    geometry = executor.add_rectangle(sketch, 100.0, 60.0)
    feature = executor.extrude(document, sketch, 3.0)
    values = (executor.connect(), document, sketch, geometry, feature, executor.rebuild(document))

    for value in values:
        assert is_dataclass(value)
        for field in fields(value):
            field_value = getattr(value, field.name)
            assert not hasattr(field_value, "_oleobj_")

    assert geometry.width_mm == 100.0
    assert feature.depth_mm == 3.0
