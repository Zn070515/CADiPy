from __future__ import annotations

import threading
from pathlib import Path

import pytest

from cadipy.api import execute
from cadipy.backends.executor import ApplicationInfo, DocumentInspection
from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import CadipyError, SessionClosedError
from cadipy.session import CadipySession


class FakeExecutor:
    executor_kind = "fake"

    def __init__(self) -> None:
        self.connected = False
        self.disconnected = False
        self.created_thread_id = threading.get_ident()

    def attach(self, *, visible: bool | None = None) -> ApplicationInfo:
        self.connected = True
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)

    def disconnect(self) -> None:
        self.disconnected = True

    def application_info(self) -> ApplicationInfo:
        return ApplicationInfo("SOLIDWORKS", "34.3.2", self.executor_kind)


@pytest.fixture
def session_executor() -> FakeExecutor:
    return FakeExecutor()


def test_session_shares_one_dispatcher_with_rpc_and_mcp(
    session_executor: FakeExecutor,
) -> None:
    executor = session_executor

    with CadipySession(executor_factory=lambda: executor, connection_mode="attach") as session:
        assert session.server.session is session
        assert session.mcp.server.session is session
        result = session.execute("application.info")
        assert result.data["executor"] == "fake"

    assert executor.disconnected is True
    with pytest.raises(SessionClosedError):
        session.execute("application.info")


def test_session_constructs_executor_and_dispatcher_on_host_thread() -> None:
    created: list[FakeExecutor] = []
    host_thread_id: list[int] = []

    def factory() -> FakeExecutor:
        created.append(FakeExecutor())
        return created[-1]

    with CadipySession(executor_factory=factory, connection_mode="attach") as session:
        host_thread_id.append(session._host.submit(threading.get_ident))
        result = session.execute("application.info")

    assert created[0].created_thread_id == host_thread_id[0]
    assert result.ok is True


def test_session_exit_disconnects_when_dispatch_raises() -> None:
    executor = FakeExecutor()

    def application_info() -> ApplicationInfo:
        raise CadipyError("application info failed")

    executor.application_info = application_info  # type: ignore[method-assign]

    with (
        pytest.raises(CadipyError, match="application info failed"),
        CadipySession(executor_factory=lambda: executor, connection_mode="attach") as session,
    ):
        session.execute("application.info")

    assert executor.disconnected is True


def test_session_reconciles_document_registry_after_close_and_open() -> None:
    executor = _DocumentExecutor()

    with CadipySession(executor_factory=lambda: executor, connection_mode="attach") as session:
        original = session.create_part()
        session.close(target=original)
        assert original.path is not None
        reopened = session.open(original.path)
        inspected = session.inspect(target=reopened)

    assert inspected.ok is True
    assert reopened.id != original.id


class _DocumentExecutor(FakeExecutor):
    def __init__(self) -> None:
        self.documents = {}
        self.counter = 0

    def list_documents(self):
        return tuple(self.documents.values())

    def create_part(self):
        from cadipy.backends.executor import DocumentHandle

        self.counter += 1
        document = DocumentHandle(
            f"doc-{self.counter}",
            DocumentType.PART,
            f"Part{self.counter}",
            Path(f"part-{self.counter}.SLDPRT"),
        )
        self.documents[document.id] = document
        return document

    def close(
        self,
        document,
        *,
        save: bool = False,
        discard: bool = False,
        require_clean: bool | None = None,
    ):
        self.documents.pop(document.id)

    def open_document(self, path, document_type=DocumentType.PART):
        from cadipy.backends.executor import DocumentHandle

        self.counter += 1
        document = DocumentHandle(f"doc-{self.counter}", document_type, f"Part{self.counter}", path)
        self.documents[document.id] = document
        return document

    def inspect_document(self, document):
        return DocumentInspection(
            document.id, document.document_type, document.path, document.title
        )


def test_api_execute_factory_uses_host_backed_session() -> None:
    created: list[FakeExecutor] = []

    def factory() -> FakeExecutor:
        executor = FakeExecutor()
        created.append(executor)
        return executor

    result = execute("application.info", executor=factory)

    assert result.ok is True
    assert created[0].created_thread_id != threading.get_ident()
    assert created[0].disconnected is True
