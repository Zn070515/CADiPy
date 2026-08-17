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
from cadipy.runtime.host import StaExecutorHost

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from cadipy.protocol.result import OperationResult


ConnectionMode = Literal["attach", "launch"]


class CadipySession:
    """Own one executor, dispatcher, resolver, and protocol adapter set."""

    def __init__(
        self,
        *,
        executor_factory: Callable[[], SolidWorksExecutor] | None = None,
        connection_mode: ConnectionMode = "attach",
        visible: bool | None = None,
        audit_recorder: AuditRecorder | None = None,
    ) -> None:
        self._executor_factory = executor_factory or PythonComSolidWorksExecutor
        self.connection_mode = connection_mode
        self.visible = visible
        self._audit_recorder = audit_recorder
        self._executor: SolidWorksExecutor | None = None
        self._registry: DocumentRegistry | None = None
        self._dispatcher: OperationDispatcher | None = None
        self._host = StaExecutorHost(self._create_executor)
        self.server = ProtocolServer.from_session(self)
        self.mcp = McpAdapter(self.server)
        self._entered = False
        self._closed = False

    def __enter__(self) -> CadipySession:  # noqa: PYI034
        if self._closed:
            raise SessionClosedError("CADiPy session cannot be re-entered after exit")
        if not self._entered:
            try:
                self._host.start()
                self._host.submit(self._initialize_runtime)
                self._host.submit(self._connect)
                self._entered = True
            except BaseException:
                self._host.close()
                self._closed = True
                raise
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._entered:
            try:
                self._host.submit(self._cleanup_runtime)
            finally:
                try:
                    self._host.close()
                finally:
                    self._closed = True
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
        return self.dispatch_request(
            {
                "id": request_id,
                "operation": operation,
                "params": params or {},
                "target": request_target,
            }
        )

    def dispatch_request(self, request: Mapping[str, Any]) -> OperationResult:
        self._ensure_open()
        return self._host.submit(lambda: self._dispatcher_or_raise().dispatch(request))

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
        executor = self._executor_or_raise()
        registry = self._registry_or_raise()
        registry.reconcile(executor.list_documents())
        return registry.resolve(binding)

    def _create_executor(self) -> SolidWorksExecutor:
        executor = self._executor_factory()
        if executor is None:
            raise RuntimeError("executor factory returned no executor")
        self._executor = executor
        return executor

    def _initialize_runtime(self) -> None:
        self._registry = DocumentRegistry()
        self._audit_recorder = self._audit_recorder or AuditRecorder()
        self._dispatcher = OperationDispatcher(
            self._executor_or_raise(),
            target_resolver=self._resolve_target,
            audit_recorder=self._audit_recorder,
        )

    def _connect(self) -> None:
        executor = self._executor_or_raise()
        if self.connection_mode == "launch":
            executor.launch(visible=True if self.visible is None else self.visible)
        else:
            executor.attach(visible=self.visible)

    def _cleanup_runtime(self) -> None:
        if self._registry is not None:
            self._registry.clear()

    def _executor_or_raise(self) -> SolidWorksExecutor:
        if self._executor is None:
            raise SessionClosedError("CADiPy executor is not initialized")
        return self._executor

    def _dispatcher_or_raise(self) -> OperationDispatcher:
        if self._dispatcher is None:
            raise SessionClosedError("CADiPy dispatcher is not initialized")
        return self._dispatcher

    def _registry_or_raise(self) -> DocumentRegistry:
        if self._registry is None:
            raise SessionClosedError("CADiPy registry is not initialized")
        return self._registry

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
