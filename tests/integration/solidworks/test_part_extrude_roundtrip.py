from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

import pytest

from cadipy.verification.postconditions import verify_rectangular_extrusion

if TYPE_CHECKING:
    from cadipy.backends.solidworks import PythonComSolidWorksExecutor


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_part_rectangle_extrude_save_close_reopen_roundtrip(
    solidworks_executor: PythonComSolidWorksExecutor,
    tmp_path,
) -> None:
    document = solidworks_executor.create_part()
    saved_path = tmp_path / "cadipy_rectangle_fixture.SLDPRT"
    closed = False
    reopened = None
    try:
        sketch = solidworks_executor.create_sketch(document, "Front Plane")
        solidworks_executor.add_rectangle(sketch, 100.0, 60.0)
        solidworks_executor.extrude(document, sketch, 3.0)
        rebuild = solidworks_executor.rebuild(document)
        assert rebuild.success is True
        inspection = solidworks_executor.inspect_document(document)
        report = verify_rectangular_extrusion(inspection, 100.0, 60.0, 3.0)
        assert report.passed, report.to_dict()

        save = solidworks_executor.save(document, saved_path)
        assert save.success is True
        assert saved_path.is_file()
        solidworks_executor.close(document)
        closed = True

        reopened = solidworks_executor.reopen(saved_path)
        reopened_rebuild = solidworks_executor.rebuild(reopened)
        assert reopened_rebuild.success is True
        reopened_inspection = solidworks_executor.inspect_document(reopened)
        reopened_report = verify_rectangular_extrusion(
            reopened_inspection,
            100.0,
            60.0,
            3.0,
        )
        assert reopened_report.passed, reopened_report.to_dict()
    finally:
        if not closed:
            with suppress(Exception):
                solidworks_executor.close(document)
        if reopened is not None:
            with suppress(Exception):
                solidworks_executor.close(reopened)
