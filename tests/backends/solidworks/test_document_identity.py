from __future__ import annotations

from pathlib import Path

from cadipy.backends.executor import DocumentHandle
from cadipy.backends.solidworks.executor import PythonComSolidWorksExecutor
from cadipy.domain.documents import DocumentType


class _StaleDocument:
    @property
    def GetPathName(self) -> str:
        raise AssertionError("stale COM document must not be inspected")

    @property
    def GetTitle(self) -> str:
        raise AssertionError("stale COM document must not be inspected")


class _LiveDocument:
    GetPathName = ""
    GetTitle = "Part1"
    GetType = 1


def test_live_document_matching_uses_serialized_identity_not_stale_com_proxy() -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle(
        id="doc-1",
        document_type=DocumentType.PART,
        title="Part1",
        path=Path("Part1.SLDPRT"),
    )
    executor._documents[handle.id] = _StaleDocument()
    executor._document_handles[handle.id] = handle

    resolved = executor._handle_for_live_document(_LiveDocument())

    assert resolved.id == handle.id


def test_saved_document_handle_retains_id_with_new_path() -> None:
    executor = PythonComSolidWorksExecutor()
    handle = DocumentHandle("doc-1", DocumentType.PART, "Part1")
    executor._document_handles[handle.id] = handle
    saved_path = Path("saved.SLDPRT")

    executor._record_saved_document_path(handle, saved_path)

    assert executor._document_handles[handle.id].id == handle.id
    assert executor._document_handles[handle.id].path == saved_path
