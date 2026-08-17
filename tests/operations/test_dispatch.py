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
from cadipy.domain.errors import InvalidArgumentError, ProtocolError, TargetNotFoundError
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
    assert result.data["verification"] == "passed"
    assert executor.calls == [
        "create_part",
        "create_sketch",
        "add_rectangle",
        "extrude",
        "rebuild",
        "inspect_document",
    ]


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


def test_mutating_existing_document_operation_requires_target_before_backend_call() -> None:
    executor = FakeExecutor()
    with pytest.raises(TargetNotFoundError):
        OperationDispatcher(executor).dispatch(
            {"id": "request-1", "operation": "part.rebuild", "params": {}}
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
