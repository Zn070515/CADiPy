from __future__ import annotations

from cadipy.backends.executor import DocumentInspection
from cadipy.domain.documents import DocumentType
from cadipy.verification.postconditions import verify_rectangular_extrusion


def _inspection(**overrides: object) -> DocumentInspection:
    values: dict[str, object] = {
        "document_id": "doc-1",
        "document_type": DocumentType.PART,
        "path": None,
        "title": "Part1",
        "sketch_names": ("Sketch1",),
        "feature_names": ("Boss-Extrude1",),
        "bounding_box_mm": (0.0, 0.0, 0.0, 100.0, 60.0, 3.0),
        "body_count": 1,
        "rectangle_width_mm": 100.0,
        "rectangle_height_mm": 60.0,
        "extrusion_depth_mm": 3.0,
        "feature_suppressed": False,
        "rebuild_success": True,
    }
    values.update(overrides)
    return DocumentInspection(**values)


def test_rectangular_extrusion_postconditions_pass_with_evidence() -> None:
    report = verify_rectangular_extrusion(_inspection(), 100.0, 60.0, 3.0)

    assert report.passed is True
    assert report.status == "passed"
    assert all(check.passed for check in report.checks)


def test_rectangular_extrusion_postconditions_fail_when_depth_is_wrong() -> None:
    report = verify_rectangular_extrusion(
        _inspection(extrusion_depth_mm=2.5),
        100.0,
        60.0,
        3.0,
    )

    assert report.passed is False
    assert report.status == "failed"
    assert any(check.name == "extrusion_depth" and not check.passed for check in report.checks)
