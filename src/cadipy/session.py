"""Persistent, backend-neutral CADiPy execution sessions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from cadipy.audit.recorder import AuditRecorder
from cadipy.backends.executor import DocumentHandle, SolidWorksExecutor
from cadipy.backends.solidworks import PythonComSolidWorksExecutor
from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import SessionClosedError
from cadipy.operations.dispatch import OperationDispatcher
from cadipy.protocol.mcp import McpAdapter
from cadipy.protocol.server import ProtocolServer
from cadipy.runtime import DocumentRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cadipy.protocol.result import OperationResult


ConnectionMode = Literal["attach", "launch"]


class CadipySession:
    """Own one executor, dispatcher, resolver, and protocol adapter set."""

    def __init__(
        self,
        *,
        executor: SolidWorksExecutor | None = None,
        connection_mode: ConnectionMode = "attach",
        visible: bool | None = None,
        audit_recorder: AuditRecorder | None = None,
    ) -> None:
        self.executor = executor or PythonComSolidWorksExecutor()
        self.connection_mode = connection_mode
        self.visible = visible
        self.registry = DocumentRegistry()
        self.audit_recorder = audit_recorder or AuditRecorder()
        self.dispatcher = OperationDispatcher(
            self.executor,
            target_resolver=self._resolve_target,
            audit_recorder=self.audit_recorder,
        )
        self.server = ProtocolServer(self.dispatcher)
        self.mcp = McpAdapter(self.server)
        self._entered = False
        self._closed = False

    def __enter__(self) -> CadipySession:  # noqa: PYI034
        if self._closed:
            raise SessionClosedError("CADiPy session cannot be re-entered after exit")
        if not self._entered:
            if self.connection_mode == "launch":
                self.executor.launch(visible=True if self.visible is None else self.visible)
            else:
                self.executor.attach(visible=self.visible)
            self._entered = True
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._entered:
            self._closed = True
            self.registry.clear()
            self.executor.disconnect()
            self._entered = False

    def execute(
        self,
        operation: str,
        *,
        params: dict[str, Any] | None = None,
        target: Mapping[str, Any] | DocumentHandle | None = None,
        request_id: str = "session-api",
    ) -> OperationResult:
        self._ensure_open()
        request_target: Mapping[str, Any] | None
        if isinstance(target, DocumentHandle):
            request_target = {"document_id": target.id}
        else:
            request_target = target
        return self.dispatcher.dispatch(
            {
                "id": request_id,
                "operation": operation,
                "params": params or {},
                "target": request_target,
            }
        )

    def create_part(self) -> DocumentHandle:
        return _handle_from_data(self.execute("document.create_part").data)

    def list_documents(self) -> tuple[DocumentHandle, ...]:
        data = self.execute("document.list").data
        if data is None:
            raise TypeError("document.list returned no data")
        return tuple(_handle_from_data(item) for item in data["documents"])

    def active_document(self) -> DocumentHandle | None:
        data = self.execute("document.active").data
        if data is None:
            raise TypeError("document.active returned no data")
        data = data["document"]
        return _handle_from_data(data) if data is not None else None

    def open(
        self,
        path: Path,
        *,
        document_type: DocumentType = DocumentType.PART,
    ) -> DocumentHandle:
        return _handle_from_data(
            self.execute(
                "document.open",
                params={"path": str(path), "document_type": document_type.value},
            ).data
        )

    def inspect(
        self,
        *,
        target: Mapping[str, Any] | DocumentHandle,
    ) -> OperationResult:
        return self.execute("document.inspect", target=target)

    def rebuild(
        self,
        *,
        target: Mapping[str, Any] | DocumentHandle,
    ) -> OperationResult:
        return self.execute("part.rebuild", target=target)

    def close(
        self,
        *,
        target: Mapping[str, Any] | DocumentHandle,
    ) -> OperationResult:
        return self.execute("document.close", target=target)

    def set_visibility(self, visible: bool) -> OperationResult:
        return self.execute("application.set_visibility", params={"visible": visible})

    def _resolve_target(self, binding: Any) -> DocumentHandle:
        self.registry.reconcile(self.executor.list_documents())
        return self.registry.resolve(binding)

    def _ensure_open(self) -> None:
        if not self._entered or self._closed:
            raise SessionClosedError("CADiPy session is not active")


def _handle_from_data(data: Any) -> DocumentHandle:
    if not isinstance(data, dict):
        raise TypeError("expected a serialized document handle")
    raw_type = data["document_type"]
    path = Path(data["path"]) if data.get("path") else None
    return DocumentHandle(
        id=str(data["id"]),
        document_type=DocumentType(raw_type),
        title=str(data["title"]),
        path=path,
        configuration=data.get("configuration"),
        active=bool(data.get("active", False)),
    )
