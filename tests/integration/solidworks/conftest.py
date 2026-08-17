from __future__ import annotations

import os
import platform
import sys
from typing import TYPE_CHECKING

import pytest

from cadipy.backends.solidworks import PythonComSolidWorksExecutor

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
        info = executor.connect()
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


def _precondition_failure(strict: bool, reason: str) -> None:
    if strict:
        pytest.fail(reason)
    pytest.skip(reason)
