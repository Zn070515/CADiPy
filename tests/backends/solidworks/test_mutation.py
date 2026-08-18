from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cadipy.backends.executor import DocumentHandle
from cadipy.backends.solidworks.executor import PythonComSolidWorksExecutor
from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import ComOperationError
from cadipy.domain.identities import DocumentIdentity
from cadipy.runtime.mutation import MutationSnapshot


@dataclass
class FakeExtension:
    finish_result: bool = True
    calls: list[tuple[str, object]] = field(default_factory=list)

    def StartRecordingUndoObject(self) -> None:
        self.calls.append(("start", None))

    def FinishRecordingUndoObject2(self, name: str, hidden: bool) -> bool:
        self.calls.append(("finish", (name, hidden)))
        return self.finish_result


@dataclass
class FakeModel:
    Extension: FakeExtension
    undo_result: bool = True
    undo_calls: list[int] = field(default_factory=list)

    def EditUndo2(self, steps: int) -> bool:
        self.undo_calls.append(steps)
        return self.undo_result


def snapshot(*, created_resource: bool = False, document_id: str = "doc-1") -> MutationSnapshot:
    return MutationSnapshot(
        target_identity=DocumentIdentity(
            document_id=document_id,
            path=None,
            title="Part1",
            document_type=DocumentType.PART,
        ),
        model_fingerprint="before",
        created_resource=created_resource,
        created_resource_id=document_id if created_resource else None,
    )


def test_created_resource_rollback_closes_only_owned_document() -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("created-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = object()
    executor._document_handles[handle.id] = handle
    closed: list[str] = []
    executor.close = lambda document: (
        closed.append(document.id),
        executor._documents.pop(document.id),
        executor._document_handles.pop(document.id),
    )

    created = snapshot(created_resource=True, document_id=handle.id)
    executor.rollback_mutation(created)

    assert closed == [handle.id]
    assert executor.verify_rollback(created) is True


def test_existing_target_rollback_finishes_recording_and_checks_fingerprint() -> None:
    extension = FakeExtension()
    model = FakeModel(extension)
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    executor._document_fingerprint = lambda document: "before"

    target = snapshot()
    executor.begin_mutation(target)
    executor.rollback_mutation(target)

    assert extension.calls == [("start", None), ("finish", ("CADiPy mutation", False))]
    assert model.undo_calls == [1]
    assert executor.verify_rollback(target) is True


def test_existing_target_is_not_closed_when_fingerprint_is_available() -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = object()
    executor._document_handles[handle.id] = handle
    executor._document_fingerprint = lambda document: "before"
    closed: list[str] = []
    executor.close = lambda document: closed.append(document.id)

    target = snapshot()
    assert executor.verify_rollback(target) is True
    assert closed == []


def test_undo_false_return_is_a_rollback_failure() -> None:
    model = FakeModel(FakeExtension(), undo_result=False)
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    target = snapshot()
    executor.begin_mutation(target)

    with pytest.raises(ComOperationError):
        executor.rollback_mutation(target)

    assert model.undo_calls == [1]


def test_finish_false_return_prevents_undo() -> None:
    extension = FakeExtension(finish_result=False)
    model = FakeModel(extension)
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    target = snapshot()
    executor.begin_mutation(target)

    with pytest.raises(ComOperationError):
        executor.rollback_mutation(target)

    assert model.undo_calls == []
