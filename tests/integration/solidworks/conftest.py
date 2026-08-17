from __future__ import annotations

import os
import platform
import sys
from contextlib import suppress
from typing import TYPE_CHECKING

import pytest

from cadipy.backends.solidworks import PythonComSolidWorksExecutor
from cadipy.session import CadipySession

if TYPE_CHECKING:
    from collections.abc import Iterator

EXPECTED_REVISION = "34.3.2"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--real-solidworks",
        action="store_true",
        default=False,
        help="require a live supported SOLIDWORKS COM session",
    )


@pytest.fixture(scope="session")
def solidworks_executor(request: pytest.FixtureRequest) -> Iterator[PythonComSolidWorksExecutor]:
    strict = (
        bool(request.config.getoption("--real-solidworks"))
        or os.getenv("CADIPY_REQUIRE_REAL_SOLIDWORKS") == "1"
    )
    if platform.system() != "Windows":
        _precondition_failure(strict, "SOLIDWORKS integration requires Windows")
    if sys.version_info[:2] != (3, 12):
        _precondition_failure(strict, "strict baseline requires Python 3.12")

    executor = PythonComSolidWorksExecutor()
    try:
        info = executor.launch() if strict else executor.attach()
    except Exception as exc:
        executor.disconnect()
        _precondition_failure(
            strict, f"SOLIDWORKS COM connection failed: {type(exc).__name__}: {exc}"
        )
        return
    if info.revision != EXPECTED_REVISION:
        executor.disconnect()
        _precondition_failure(
            strict,
            "unsupported SOLIDWORKS revision: "
            f"expected {EXPECTED_REVISION}, observed {info.revision}",
        )
        return

    try:
        yield executor
    finally:
        executor.disconnect()


@pytest.fixture
def solidworks_session(
    request: pytest.FixtureRequest,
    solidworks_executor: PythonComSolidWorksExecutor,
) -> Iterator[CadipySession]:
    strict = (
        bool(request.config.getoption("--real-solidworks"))
        or os.getenv("CADIPY_REQUIRE_REAL_SOLIDWORKS") == "1"
    )
    if platform.system() != "Windows":
        _precondition_failure(strict, "SOLIDWORKS integration requires Windows")
    if sys.version_info[:2] != (3, 12):
        _precondition_failure(strict, "strict baseline requires Python 3.12")

    connection_mode = "launch" if solidworks_executor.application_info().owned else "attach"
    session = CadipySession(executor=solidworks_executor, connection_mode=connection_mode)
    try:
        session.__enter__()
        if solidworks_executor.application_info().revision != EXPECTED_REVISION:
            raise RuntimeError(
                f"unsupported SOLIDWORKS revision: expected {EXPECTED_REVISION}, "
                f"observed {solidworks_executor.application_info().revision}"
            )
        initial_ids = {document.id for document in session.list_documents()}
    except Exception as exc:
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
                    with suppress(Exception):
                        session.close(target=document)
        finally:
            session.__exit__(None, None, None)


def _precondition_failure(strict: bool, reason: str) -> None:
    if strict:
        pytest.fail(reason)
    pytest.skip(reason)
