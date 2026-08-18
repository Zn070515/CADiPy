from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import time
from contextlib import suppress
from typing import TYPE_CHECKING, NoReturn

import pytest

from cadipy.backends.solidworks import PythonComSolidWorksExecutor
from cadipy.session import CadipySession

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

EXPECTED_REVISION = "34.3.2"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--real-solidworks",
        action="store_true",
        default=False,
        help="require a live supported SOLIDWORKS COM session",
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    ownership_node = "test_attached_user_owned_application_survives_session_disconnect"
    items.sort(key=lambda item: 0 if ownership_node in item.nodeid else 1)


class _DiagnosticExecutor(PythonComSolidWorksExecutor):
    """Test-only semantic hook that records executor call thread identities."""

    def __init__(self, operation_thread_ids: list[int]) -> None:
        super().__init__()
        self.operation_thread_ids = operation_thread_ids

    def __getattribute__(self, name: str):  # type: ignore[no-untyped-def]
        attribute = super().__getattribute__(name)
        if name.startswith("_") or name in {"operation_thread_ids"}:
            return attribute
        if not callable(attribute):
            return attribute

        def traced(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            object.__getattribute__(self, "operation_thread_ids").append(threading.get_ident())
            return attribute(*args, **kwargs)

        return traced


class _DiagnosticExecutorFactory:
    def __init__(self) -> None:
        self.operation_thread_ids: list[int] = []

    def __call__(self) -> _DiagnosticExecutor:
        return _DiagnosticExecutor(self.operation_thread_ids)


class _UserOwnedAttachExecutor(PythonComSolidWorksExecutor):
    """Test-only attach seam for SOLIDWORKS builds that do not publish the ROT."""

    def attach(self, *, visible: bool | None = None):  # type: ignore[no-untyped-def]
        import win32com.client

        return self._connect(
            lambda: win32com.client.Dispatch("SldWorks.Application"),
            mode="attach",
            owned=False,
            visible=visible,
        )


@pytest.fixture(scope="session")
def solidworks_executor_factory() -> _DiagnosticExecutorFactory:
    """Create each backend only when the session's STA host invokes the factory."""

    return _DiagnosticExecutorFactory()


@pytest.fixture
def user_owned_executor_factory() -> type[_UserOwnedAttachExecutor]:
    return _UserOwnedAttachExecutor


@pytest.fixture(scope="session")
def solidworks_session(
    request: pytest.FixtureRequest,
    solidworks_executor_factory: _DiagnosticExecutorFactory,
) -> Iterator[CadipySession]:
    strict = _strict_mode(request)
    _validate_environment(strict)
    baseline_process_ids = _solidworks_process_ids()
    if strict and baseline_process_ids:
        _precondition_failure(
            strict,
            "strict SOLIDWORKS session found a pre-existing process: "
            f"{sorted(baseline_process_ids)}",
        )

    session = CadipySession(
        executor_factory=solidworks_executor_factory,
        connection_mode="launch" if strict else "attach",
        visible=False if strict else None,
    )
    entered = False
    try:
        session.__enter__()
        entered = True
        info = session.execute("application.info")
        if not info.ok or info.data is None:
            raise RuntimeError("application.info did not return a successful domain result")
        if info.data["revision"] != EXPECTED_REVISION:
            raise RuntimeError(
                "unsupported SOLIDWORKS revision: "
                f"expected {EXPECTED_REVISION}, observed {info.data['revision']}"
            )
        if strict and info.data["owned"] is not True:
            raise RuntimeError("strict session did not own the launched SOLIDWORKS application")
        owned_process_ids = _solidworks_process_ids() - baseline_process_ids
        initial_ids = {document.id for document in session.list_documents()}
    except Exception as exc:
        if entered:
            with suppress(Exception):
                session.__exit__(None, None, None)
        _precondition_failure(
            strict,
            f"SOLIDWORKS session setup failed: {type(exc).__name__}: {exc}",
        )
        return

    try:
        yield session
    finally:
        try:
            for document in session.list_documents():
                if document.id not in initial_ids:
                    session.close(target=document)
        finally:
            cleanup_error: BaseException | None = None
            try:
                session.__exit__(None, None, None)
            except BaseException as exc:
                cleanup_error = exc
            if strict:
                _wait_for_process_exit(owned_process_ids)
            if cleanup_error is not None:
                raise cleanup_error


@pytest.fixture
def user_owned_application(request: pytest.FixtureRequest) -> Iterator[Callable[[], bool]]:
    """Create a user-owned app after workflow preflight for attach ownership evidence."""

    strict = _strict_mode(request)
    if not strict:
        pytest.skip("user-owned lifecycle evidence requires strict SOLIDWORKS mode")
    _validate_environment(strict)
    baseline_process_ids = _solidworks_process_ids()
    if baseline_process_ids:
        _precondition_failure(
            strict,
            "user-owned lifecycle test found a pre-existing SOLIDWORKS process: "
            f"{sorted(baseline_process_ids)}",
        )
    application = None
    try:
        import win32com.client

        application = win32com.client.Dispatch("SldWorks.Application")
        application.Visible = False
        revision = str(application.RevisionNumber)
        owned_process_ids = _solidworks_process_ids() - baseline_process_ids
        if revision != EXPECTED_REVISION:
            raise RuntimeError(
                "unsupported SOLIDWORKS revision: "
                f"expected {EXPECTED_REVISION}, observed {revision}"
            )
    except Exception as exc:
        if application is not None:
            with suppress(Exception):
                application.ExitApp()
        _precondition_failure(
            strict,
            f"user-owned SOLIDWORKS setup failed: {type(exc).__name__}: {exc}",
        )
        return

    def is_available() -> bool:
        try:
            return str(application.RevisionNumber) == EXPECTED_REVISION
        except Exception:
            return False

    try:
        yield is_available
    finally:
        if owned_process_ids.intersection(_solidworks_process_ids()):
            with suppress(Exception):
                application.ExitApp()
        application = None
        _wait_for_process_exit(owned_process_ids)


def _strict_mode(request: pytest.FixtureRequest) -> bool:
    return (
        bool(request.config.getoption("--real-solidworks"))
        or os.getenv("CADIPY_REQUIRE_REAL_SOLIDWORKS") == "1"
    )


def _validate_environment(strict: bool) -> None:
    if platform.system() != "Windows":
        _precondition_failure(strict, "SOLIDWORKS integration requires Windows")
    if sys.version_info[:2] != (3, 12):
        _precondition_failure(strict, "strict baseline requires Python 3.12")


def _precondition_failure(strict: bool, reason: str) -> NoReturn:
    if strict:
        pytest.fail(reason)
    pytest.skip(reason)


def _solidworks_process_ids() -> set[int]:
    output = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
        text=True,
        stderr=subprocess.STDOUT,
    )
    process_ids: set[int] = set()
    for line in output.splitlines():
        fields = [field.strip('"') for field in line.split('","')]
        if len(fields) >= 2 and fields[0].casefold() == "sldworks.exe":
            process_ids.add(int(fields[1]))
    return process_ids


def _wait_for_process_exit(process_ids: set[int]) -> None:
    if not process_ids:
        return
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if not process_ids.intersection(_solidworks_process_ids()):
            return
        time.sleep(0.25)
    remaining = sorted(process_ids.intersection(_solidworks_process_ids()))
    raise RuntimeError(f"CADiPy-owned SOLIDWORKS processes did not exit: {remaining}")
