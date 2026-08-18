from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from cadipy.protocol.result import OperationResult
    from cadipy.session import CadipySession


def run_rectangular_contract_via_session(
    session: CadipySession,
    tmp_path: Path,
) -> OperationResult:
    """Run the persisted 100x60x3 mm contract through the public session API."""

    return session.execute(
        "part.create_rectangular_extrude",
        params={
            "width_mm": 100.0,
            "height_mm": 60.0,
            "depth_mm": 3.0,
            "save_path": str(tmp_path / "cadipy_rectangle_fixture.SLDPRT"),
        },
        request_id="strict-rectangular-roundtrip",
    )


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_part_rectangle_extrude_save_close_reopen_roundtrip(
    solidworks_session,
    tmp_path,
) -> None:
    result = run_rectangular_contract_via_session(solidworks_session, tmp_path)

    assert result.ok is True
    assert result.execution is not None
    assert result.execution.phase.value == "committed"
    assert result.data is not None
    assert result.data["rebuild"] == "ok"
    assert result.data["reopened_rebuild"] == "ok"
    assert result.data["verification"] == "passed"
    assert result.data["reopened_verification"]["status"] == "passed"
    assert (tmp_path / "cadipy_rectangle_fixture.SLDPRT").is_file()
