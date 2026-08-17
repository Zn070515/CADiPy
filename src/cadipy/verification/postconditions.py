"""Reusable postcondition checks that inspect domain reports, not COM objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from cadipy.domain.documents import DocumentType

if TYPE_CHECKING:
    from cadipy.backends.executor import DocumentInspection


@dataclass(frozen=True, slots=True)
class VerificationCheck:
    name: str
    passed: bool
    expected: Any
    observed: Any
    details: str = ""


@dataclass(frozen=True, slots=True)
class VerificationReport:
    passed: bool
    status: str
    checks: tuple[VerificationCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status,
            "checks": [asdict(check) for check in self.checks],
        }


def verify_rectangular_extrusion(
    inspection: DocumentInspection,
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    *,
    tolerance_mm: float = 0.01,
) -> VerificationReport:
    checks = (
        _check(
            "document_type",
            inspection.document_type is DocumentType.PART,
            "part",
            inspection.document_type.value,
        ),
        _check("sketch_exists", bool(inspection.sketch_names), True, bool(inspection.sketch_names)),
        _check(
            "feature_exists", bool(inspection.feature_names), True, bool(inspection.feature_names)
        ),
        _check("body_count", inspection.body_count == 1, 1, inspection.body_count),
        _within("rectangle_width", inspection.rectangle_width_mm, width_mm, tolerance_mm),
        _within("rectangle_height", inspection.rectangle_height_mm, height_mm, tolerance_mm),
        _within("extrusion_depth", inspection.extrusion_depth_mm, depth_mm, tolerance_mm),
        _check(
            "feature_unsuppressed",
            inspection.feature_suppressed is False,
            False,
            inspection.feature_suppressed,
        ),
        _check(
            "rebuild",
            inspection.rebuild_success is True,
            True,
            inspection.rebuild_success,
        ),
    )
    passed = all(check.passed for check in checks)
    return VerificationReport(passed=passed, status="passed" if passed else "failed", checks=checks)


def _within(
    name: str, observed: float | None, expected: float, tolerance: float
) -> VerificationCheck:
    passed = observed is not None and abs(observed - expected) <= tolerance
    return _check(name, passed, expected, observed, f"tolerance_mm={tolerance}")


def _check(
    name: str, passed: bool, expected: Any, observed: Any, details: str = ""
) -> VerificationCheck:
    return VerificationCheck(name, passed, expected, observed, details)
