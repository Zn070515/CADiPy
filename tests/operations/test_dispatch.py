from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from cadipy.audit.recorder import AuditRecorder
from cadipy.backends.executor import (
    ApplicationInfo,
    DocumentHandle,
    DocumentInspection,
    FeatureHandle,
    GeometryHandle,
    RebuildReport,
    SaveReport,
    SketchHandle,
)
from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import (
    DocumentTypeError,
    InvalidArgumentError,
    ProtocolError,
    TargetNotFoundError,
    VerificationError,
)
from cadipy.domain.execution import ExecutionPhase
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
from cadipy.operations.dispatch import OperationDispatcher


class FakeExecutor:
    executor_kind = "fake"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def connect(self) -> ApplicationInfo:
        self.calls.append("connect")
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)

    def create_part(self) -> DocumentHandle:
        self.calls.append("create_part")
        return DocumentHandle("doc-1", DocumentType.PART, "Part1")

    def create_sketch(self, document: DocumentHandle, plane: str) -> SketchHandle:
        self.calls.append("create_sketch")
        return SketchHandle("sketch-1", document.id, "Sketch1", plane)

    def add_rectangle(
        self, sketch: SketchHandle, width_mm: float, height_mm: float
    ) -> GeometryHandle:
        self.calls.append("add_rectangle")
        return GeometryHandle("geometry-1", sketch.id, width_mm, height_mm)

    def extrude(
        self, document: DocumentHandle, sketch: SketchHandle, depth_mm: float
    ) -> FeatureHandle:
        self.calls.append("extrude")
        return FeatureHandle("feature-1", document.id, "Boss-Extrude1", "extrusion", depth_mm)

    def rebuild(self, document: DocumentHandle) -> RebuildReport:
        self.calls.append("rebuild")
        return RebuildReport(True)

    def save(self, document: DocumentHandle, path: Path) -> SaveReport:
        self.calls.append("save")
        return SaveReport(True, path)

    def close(self, document: DocumentHandle) -> None:
        self.calls.append("close")

    def reopen(self, path: Path) -> DocumentHandle:
        self.calls.append("reopen")
        return DocumentHandle("doc-2", DocumentType.PART, path.stem, path)

    def inspect_document(self, document: DocumentHandle) -> DocumentInspection:
        self.calls.append("inspect_document")
        return DocumentInspection(
            document.id,
            DocumentType.PART,
            document.path,
            document.title,
            ("Sketch1",),
            ("Boss-Extrude1",),
            (0.0, 0.0, 0.0, 100.0, 60.0, 3.0),
            1,
            100.0,
            60.0,
            3.0,
            False,
            True,
        )


def test_dispatcher_executes_geometry_operation_through_the_port() -> None:
    executor = FakeExecutor()
    result = OperationDispatcher(executor).dispatch(
        {
            "id": "request-1",
            "operation": "part.create_rectangular_extrude",
            "params": {"width_mm": 100.0, "height_mm": 60.0, "depth_mm": 3.0},
        }
    )

    assert result.ok is True
    assert result.execution is not None
    assert result.execution.phase is ExecutionPhase.COMMITTED
    assert result.data["verification"] == "passed"
    assert executor.calls == [
        "create_part",
        "create_sketch",
        "add_rectangle",
        "extrude",
        "rebuild",
        "inspect_document",
    ]


def test_required_verification_failure_raises_with_failed_execution_report() -> None:
    executor = FailingInspectionExecutor()

    with pytest.raises(VerificationError) as caught:
        OperationDispatcher(executor).dispatch(
            {
                "id": "request-failure",
                "operation": "part.create_rectangular_extrude",
                "params": {"width_mm": 100.0, "height_mm": 60.0, "depth_mm": 3.0},
            }
        )

    assert caught.value.execution.phase is ExecutionPhase.VERIFICATION_FAILED
    assert caught.value.execution.state_certainty == "uncertain"


def test_dimension_value_mismatch_fails_direct_dispatch_verification() -> None:
    executor = SketchFakeExecutor()
    document = DocumentHandle("doc-a", DocumentType.PART, "PartA")
    dispatcher = OperationDispatcher(executor, target_resolver=lambda binding: document)

    with pytest.raises(VerificationError) as caught:
        dispatcher.dispatch(
            {
                "id": "dimension-mismatch",
                "operation": "sketch.set_dimension",
                "target": {"document_id": document.id},
                "params": {
                    "sketch": {
                        "id": "sketch-1",
                        "document_id": document.id,
                        "name": "Sketch1",
                        "plane": "Front Plane",
                    },
                    "dimension": {
                        "id": "dimension-1",
                        "sketch_id": "sketch-1",
                        "dimension_type": "horizontal_distance",
                        "name": "D1@Sketch1",
                        "value_mm": 100.0,
                    },
                    "value_mm": 100.0,
                },
            }
        )

    assert caught.value.code == "verification_failed"
    assert caught.value.execution.phase is ExecutionPhase.VERIFICATION_FAILED


def test_visibility_mismatch_fails_direct_dispatch_verification() -> None:
    with pytest.raises(VerificationError) as caught:
        OperationDispatcher(VisibilityMismatchExecutor()).dispatch(
            {
                "id": "visibility-mismatch",
                "operation": "application.set_visibility",
                "params": {"visible": True},
            }
        )

    assert caught.value.code == "verification_failed"
    assert caught.value.execution.phase is ExecutionPhase.VERIFICATION_FAILED


def test_dispatcher_rejects_unknown_or_malformed_operations() -> None:
    dispatcher = OperationDispatcher(FakeExecutor())
    with pytest.raises(ProtocolError):
        dispatcher.dispatch({"id": "request-1", "operation": "part.unknown", "params": {}})
    with pytest.raises(InvalidArgumentError):
        dispatcher.dispatch(
            {
                "id": "request-1",
                "operation": "part.create_rectangular_extrude",
                "params": {"width_mm": 100.0, "height_mm": 60.0},
            }
        )
    with pytest.raises(InvalidArgumentError):
        dispatcher.dispatch(
            {
                "id": "request-1",
                "operation": "sketch.add_relation",
                "target": {"document_id": "doc-1"},
                "params": {"anchor_origin": "yes"},
            }
        )


def test_mutating_existing_document_operation_requires_target_before_backend_call() -> None:
    executor = FakeExecutor()
    with pytest.raises(TargetNotFoundError):
        OperationDispatcher(executor).dispatch(
            {"id": "request-1", "operation": "part.rebuild", "params": {}}
        )
    assert executor.calls == []


def test_part_operation_rejects_assembly_target() -> None:
    executor = FakeExecutor()
    assembly = DocumentHandle("assembly-1", DocumentType.ASSEMBLY, "Assembly1")
    dispatcher = OperationDispatcher(executor, target_resolver=lambda binding: assembly)

    with pytest.raises(DocumentTypeError):
        dispatcher.dispatch(
            {
                "id": "request-1",
                "operation": "part.rebuild",
                "params": {},
                "target": {"document_id": assembly.id},
            }
        )
    assert executor.calls == []


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_dispatcher_rejects_non_finite_numeric_cad_params_before_executor_call(
    value: float,
) -> None:
    executor = FakeExecutor()

    with pytest.raises(InvalidArgumentError):
        OperationDispatcher(executor).dispatch(
            {
                "id": "request-1",
                "operation": "part.create_rectangular_extrude",
                "params": {
                    "width_mm": 100.0,
                    "height_mm": 60.0,
                    "depth_mm": value,
                },
            }
        )
    assert executor.calls == []


def test_dispatcher_records_public_audit_evidence() -> None:
    recorder = AuditRecorder()
    result = OperationDispatcher(FakeExecutor(), audit_recorder=recorder).dispatch(
        {
            "id": "request-1",
            "operation": "diagnostics.connect",
            "params": {},
        }
    )

    assert result.ok is True
    assert recorder.to_list()[0]["executor_kind"] == "fake"


def test_dispatcher_handles_document_lifecycle_operations_from_one_registry() -> None:
    executor = LifecycleFakeExecutor()
    target = DocumentHandle("doc-a", DocumentType.PART, "PartA")
    dispatcher = OperationDispatcher(executor, target_resolver=lambda binding: target)

    listed = dispatcher.dispatch({"id": "list-1", "operation": "document.list", "params": {}})
    closed = dispatcher.dispatch(
        {
            "id": "close-1",
            "operation": "document.close",
            "target": {"document_id": "doc-a"},
            "params": {},
        }
    )

    assert listed.data["documents"][0]["id"] == "doc-a"
    assert closed.ok is True
    assert executor.closed_ids == ["doc-a"]


def test_document_open_rejects_unknown_document_type_as_domain_error() -> None:
    with pytest.raises(InvalidArgumentError):
        OperationDispatcher(LifecycleFakeExecutor()).dispatch(
            {
                "id": "open-1",
                "operation": "document.open",
                "params": {"path": "PartA.SLDPRT", "document_type": "surface"},
            }
        )


def test_dispatcher_exposes_composable_sketch_contracts_from_one_registry() -> None:
    executor = SketchFakeExecutor()
    document = DocumentHandle("doc-a", DocumentType.PART, "PartA")
    dispatcher = OperationDispatcher(executor, target_resolver=lambda binding: document)
    target = {"document_id": document.id}
    sketch_value = {
        "id": "sketch-1",
        "document_id": document.id,
        "name": "Sketch1",
        "plane": "Front Plane",
    }
    entity_value = {
        "id": "entity-1",
        "document_id": document.id,
        "sketch_id": "sketch-1",
        "entity_type": "line",
        "persistent_ref": "AQ==",
        "start_x_mm": 0.0,
        "start_y_mm": 0.0,
        "end_x_mm": 100.0,
        "end_y_mm": 0.0,
    }
    dimension_value = {
        "id": "dimension-1",
        "sketch_id": "sketch-1",
        "dimension_type": "horizontal_distance",
        "name": "D1@Sketch1",
        "value_mm": 100.0,
    }

    assert dispatcher.dispatch(
        {
            "operation": "sketch.create",
            "target": target,
            "params": {"plane": "Front Plane"},
        }
    ).ok
    assert dispatcher.dispatch({"operation": "sketch.list", "target": target, "params": {}}).ok
    assert dispatcher.dispatch(
        {"operation": "sketch.inspect", "target": target, "params": {"sketch": sketch_value}}
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.add_line",
            "target": target,
            "params": {
                "sketch": sketch_value,
                "start_x_mm": 0.0,
                "start_y_mm": 0.0,
                "end_x_mm": 100.0,
                "end_y_mm": 0.0,
            },
        }
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.add_rectangle",
            "target": target,
            "params": {"sketch": sketch_value, "width_mm": 100.0, "height_mm": 60.0},
        }
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.add_circle",
            "target": target,
            "params": {
                "sketch": sketch_value,
                "center_x_mm": 0.0,
                "center_y_mm": 0.0,
                "radius_mm": 5.0,
            },
        }
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.add_arc",
            "target": target,
            "params": {
                "sketch": sketch_value,
                "center_x_mm": 0.0,
                "center_y_mm": 0.0,
                "start_x_mm": 5.0,
                "start_y_mm": 0.0,
                "end_x_mm": 0.0,
                "end_y_mm": 5.0,
            },
        }
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.add_relation",
            "target": target,
            "params": {
                "sketch": sketch_value,
                "relation_type": "horizontal",
                "entities": [entity_value],
            },
        }
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.add_dimension",
            "target": target,
            "params": {
                "sketch": sketch_value,
                "dimension_type": "horizontal_distance",
                "entities": [entity_value],
                "value_mm": 100.0,
                "position_x_mm": 50.0,
                "position_y_mm": -10.0,
            },
        }
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.set_dimension",
            "target": target,
            "params": {"sketch": sketch_value, "dimension": dimension_value, "value_mm": 120.0},
        }
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.inspect_entity",
            "target": target,
            "params": {"sketch": sketch_value, "entity": entity_value},
        }
    ).ok
    assert dispatcher.dispatch(
        {
            "operation": "sketch.inspect_dimension",
            "target": target,
            "params": {"sketch": sketch_value, "dimension": dimension_value},
        }
    ).ok


class SketchFakeExecutor(FakeExecutor):
    def list_sketches(self, document: DocumentHandle) -> tuple[SketchHandle, ...]:
        return (SketchHandle("sketch-1", document.id, "Sketch1", "Front Plane"),)

    def inspect_sketch(self, document: DocumentHandle, sketch: SketchHandle) -> SketchInspection:
        return SketchInspection(sketch.id, sketch.name, sketch.plane, 4, 4, 2, False)

    def add_line(self, *args: object) -> SketchEntityHandle:
        return self._entity()

    def add_sketch_rectangle(self, *args: object) -> tuple[SketchEntityHandle, ...]:
        return (self._entity(),) * 4

    def add_circle(self, *args: object) -> SketchEntityHandle:
        return self._entity(SketchEntityType.CIRCLE)

    def add_arc(self, *args: object) -> SketchEntityHandle:
        return self._entity(SketchEntityType.ARC)

    def add_relation(self, *args: object, **kwargs: object) -> RelationHandle:
        return RelationHandle("relation-1", "sketch-1", RelationType.HORIZONTAL, ("entity-1",))

    def add_dimension(self, *args: object) -> DimensionHandle:
        return DimensionHandle(
            "dimension-1", "sketch-1", DimensionType.HORIZONTAL_DISTANCE, "D1@Sketch1", 100.0
        )

    def set_dimension(self, *args: object) -> DimensionHandle:
        return DimensionHandle(
            "dimension-1", "sketch-1", DimensionType.HORIZONTAL_DISTANCE, "D1@Sketch1", 120.0
        )

    def inspect_entity(self, *args: object) -> SketchEntityInspection:
        return SketchEntityInspection(self._entity(), SketchEntityType.LINE, 1)

    def inspect_dimension(self, *args: object) -> DimensionInspection:
        return DimensionInspection(
            DimensionHandle(
                "dimension-1", "sketch-1", DimensionType.HORIZONTAL_DISTANCE, "D1@Sketch1", 100.0
            ),
            100.0,
        )

    @staticmethod
    def _entity(entity_type: SketchEntityType = SketchEntityType.LINE) -> SketchEntityHandle:
        return SketchEntityHandle(
            "entity-1",
            "doc-a",
            "sketch-1",
            entity_type,
            "AQ==",
            start_x_mm=0.0,
            start_y_mm=0.0,
            end_x_mm=100.0,
            end_y_mm=0.0,
        )


class LifecycleFakeExecutor(FakeExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.closed_ids: list[str] = []

    def list_documents(self) -> tuple[DocumentHandle, ...]:
        self.calls.append("list_documents")
        return (DocumentHandle("doc-a", DocumentType.PART, "PartA"),)

    def active_document(self) -> DocumentHandle:
        self.calls.append("active_document")
        return DocumentHandle("doc-a", DocumentType.PART, "PartA", active=True)

    def close(self, document: DocumentHandle) -> None:
        self.calls.append("close")
        self.closed_ids.append(document.id)


class FailingInspectionExecutor(FakeExecutor):
    def inspect_document(self, document: DocumentHandle) -> DocumentInspection:
        return DocumentInspection(
            document.id,
            DocumentType.PART,
            None,
            document.title,
            ("Sketch1",),
            ("Boss-Extrude1",),
            (0.0, 0.0, 0.0, 100.0, 60.0, 2.5),
            1,
            100.0,
            60.0,
            2.5,
            False,
            True,
        )


class VisibilityMismatchExecutor:
    executor_kind = "fake"

    def set_visibility(self, visible: bool) -> ApplicationInfo:
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind, visible=False)
