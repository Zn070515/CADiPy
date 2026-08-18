from __future__ import annotations

from dataclasses import dataclass, field, replace

import pytest

from cadipy.backends.executor import DocumentHandle
from cadipy.backends.solidworks import documents as solidworks_documents
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

    def EditUndo2(self, steps: int) -> object:
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


def test_uncertain_mutation_state_persists_until_reconciliation() -> None:
    executor = PythonComSolidWorksExecutor()

    assert executor.mutation_state_uncertain() is False
    executor.mark_mutation_uncertain()
    assert executor.mutation_state_uncertain() is True

    executor.reconcile_mutation()
    assert executor.mutation_state_uncertain() is False


def test_created_resource_rollback_closes_only_owned_document(monkeypatch) -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("created-1", DocumentType.PART, "Part1")
    model = object()
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    executor._created_document_ids.add(handle.id)
    executor._created_documents[handle.id] = model
    executor._application = object()
    closed: list[str] = []
    executor.close = lambda document: (
        closed.append(document.id),
        executor._documents.pop(document.id),
        executor._document_handles.pop(document.id),
    )
    monkeypatch.setattr(solidworks_documents, "list_open_documents", lambda application: ())

    created = snapshot(created_resource=True, document_id=handle.id)
    executor.rollback_mutation(created)

    assert closed == [handle.id]
    assert executor.verify_rollback(created) is True


def test_unowned_created_resource_cannot_be_closed() -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("user-doc", DocumentType.PART, "UserPart")
    executor._documents[handle.id] = object()
    executor._document_handles[handle.id] = handle

    with pytest.raises(ComOperationError):
        executor.rollback_mutation(snapshot(created_resource=True, document_id=handle.id))


def test_mismatched_created_resource_id_is_rejected() -> None:
    executor = PythonComSolidWorksExecutor()
    pending = snapshot(created_resource=True, document_id="pending")
    executor.begin_mutation(pending)

    with pytest.raises(ComOperationError):
        executor.record_created_resource("not-created")


def test_close_failure_does_not_verify_created_resource_rollback(monkeypatch) -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("created-1", DocumentType.PART, "Part1")
    model = object()
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    executor._created_document_ids.add(handle.id)
    executor._created_documents[handle.id] = model
    executor.close = lambda document: (_ for _ in ()).throw(RuntimeError("close failed"))
    executor._application = object()
    monkeypatch.setattr(solidworks_documents, "list_open_documents", lambda application: (model,))

    created = snapshot(created_resource=True, document_id=handle.id)
    with pytest.raises(RuntimeError):
        executor.rollback_mutation(created)

    assert executor.verify_rollback(created) is False


def test_local_cache_removal_without_live_close_is_unverifiable(monkeypatch) -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("created-1", DocumentType.PART, "Part1")
    model = object()
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    executor._created_document_ids.add(handle.id)
    executor._created_documents[handle.id] = model
    executor._application = object()
    executor.close = lambda document: (
        executor._documents.pop(document.id),
        executor._document_handles.pop(document.id),
    )
    monkeypatch.setattr(solidworks_documents, "list_open_documents", lambda application: (model,))

    created = snapshot(created_resource=True, document_id=handle.id)
    executor.rollback_mutation(created)

    assert executor.verify_rollback(created) is False


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


def test_existing_target_fingerprint_uses_resolved_document_handle() -> None:
    class InspectableModel(FakeModel):
        GetType = 1
        GetTitle = "Part1"
        GetPathName = ""
        FirstFeature = None

        def GetBodies2(self, body_type: int, visible: bool) -> tuple[object, ...]:
            return ()

        def GetPartBox(self, include_hidden: bool) -> tuple[float, ...]:
            return (0.0, 0.0, 0.0, 0.1, 0.1, 0.1)

    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    model = InspectableModel(FakeExtension(), undo_result=None)
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle

    target = replace(snapshot(), model_fingerprint=executor._document_fingerprint(handle))
    executor.begin_mutation(target)
    executor.rollback_mutation(target)

    assert executor.verify_rollback(target) is True


def test_existing_target_is_not_closed_when_fingerprint_is_available() -> None:
    model = FakeModel(FakeExtension(), undo_result=None)
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    executor._document_fingerprint = lambda document: "before"
    closed: list[str] = []
    executor.close = lambda document: closed.append(document.id)

    target = snapshot()
    executor.begin_mutation(target)
    executor.rollback_mutation(target)
    assert executor.verify_rollback(target) is True
    assert closed == []


def test_existing_target_without_undo_attempt_cannot_verify_rollback() -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = object()
    executor._document_handles[handle.id] = handle
    executor._document_fingerprint = lambda document: "before"

    assert executor.verify_rollback(snapshot()) is False


def test_void_undo_return_is_verified_by_fingerprint() -> None:
    model = FakeModel(FakeExtension(), undo_result=None)
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    executor._document_fingerprint = lambda document: "before"
    target = snapshot()
    executor.begin_mutation(target)

    executor.rollback_mutation(target)

    assert model.undo_calls == [1]
    assert executor.verify_rollback(target) is True


def test_void_undo_with_changed_fingerprint_is_not_rolled_back() -> None:
    model = FakeModel(FakeExtension(), undo_result=None)
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    executor._document_fingerprint = lambda document: "after"
    target = snapshot()
    executor.begin_mutation(target)

    executor.rollback_mutation(target)

    assert executor.verify_rollback(target) is False


def test_missing_fingerprint_is_state_unverifiable() -> None:
    model = FakeModel(FakeExtension(), undo_result=None)
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = model
    executor._document_handles[handle.id] = handle
    target = replace(snapshot(), model_fingerprint=None)
    executor.begin_mutation(target)

    executor.rollback_mutation(target)

    assert executor.verify_rollback(target) is False


def test_missing_undo_support_cannot_report_rolled_back() -> None:
    class ModelWithoutUndo:
        def __init__(self) -> None:
            self.Extension = FakeExtension()

    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = ModelWithoutUndo()
    executor._document_handles[handle.id] = handle
    target = snapshot()
    executor.begin_mutation(target)

    with pytest.raises(ComOperationError):
        executor.rollback_mutation(target)

    assert executor._undo_recording is False


def test_missing_undo_recording_support_is_rejected_at_begin() -> None:
    class ModelWithoutRecording:
        Extension = object()

    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._documents[handle.id] = ModelWithoutRecording()
    executor._document_handles[handle.id] = handle

    with pytest.raises(ComOperationError):
        executor.begin_mutation(snapshot())

    assert executor._undo_recording is False


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
