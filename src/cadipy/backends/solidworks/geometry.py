"""Internal sketch and feature calls for the semantic executor."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from cadipy.domain.errors import ComOperationError
from cadipy.domain.units import mm_to_sw_m


def create_sketch(document: Any, plane: str) -> Any:
    try:
        _select_plane(document, plane)
        sketch_manager = document.SketchManager
        sketch_manager.InsertSketch(True)
    except ComOperationError:
        raise
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not create the sketch",
            operation="solidworks.create_sketch",
            details={"plane": plane},
        ) from exc
    else:
        return sketch_manager.ActiveSketch


def add_rectangle(document: Any, width_mm: float, height_mm: float) -> Any:
    width = mm_to_sw_m(width_mm)
    height = mm_to_sw_m(height_mm)
    try:
        sketch_manager = document.SketchManager
        segments = sketch_manager.CreateCornerRectangle(
            -width / 2.0,
            height / 2.0,
            0.0,
            width / 2.0,
            -height / 2.0,
            0.0,
        )
        _require_value(
            segments,
            message="SOLIDWORKS returned no rectangle segments",
            operation="solidworks.add_rectangle",
        )
        sketch_manager.InsertSketch(False)
    except ComOperationError:
        raise
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not create the rectangle",
            operation="solidworks.add_rectangle",
        ) from exc
    else:
        return segments


def add_line(
    document: Any,
    start_x_mm: float,
    start_y_mm: float,
    end_x_mm: float,
    end_y_mm: float,
) -> Any:
    try:
        segment = document.SketchManager.CreateLine(
            mm_to_sw_m(start_x_mm),
            mm_to_sw_m(start_y_mm),
            0.0,
            mm_to_sw_m(end_x_mm),
            mm_to_sw_m(end_y_mm),
            0.0,
        )
        _require_value(
            segment,
            message="SOLIDWORKS returned no line segment",
            operation="solidworks.add_line",
        )
    except ComOperationError:
        raise
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not create the line",
            operation="solidworks.add_line",
        ) from exc
    return segment


def add_circle(
    document: Any,
    center_x_mm: float,
    center_y_mm: float,
    radius_mm: float,
) -> Any:
    try:
        segment = document.SketchManager.CreateCircleByRadius(
            mm_to_sw_m(center_x_mm),
            mm_to_sw_m(center_y_mm),
            0.0,
            mm_to_sw_m(radius_mm),
        )
        _require_value(
            segment,
            message="SOLIDWORKS returned no circle segment",
            operation="solidworks.add_circle",
        )
    except ComOperationError:
        raise
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not create the circle",
            operation="solidworks.add_circle",
        ) from exc
    return segment


def add_arc(
    document: Any,
    center_x_mm: float,
    center_y_mm: float,
    start_x_mm: float,
    start_y_mm: float,
    end_x_mm: float,
    end_y_mm: float,
    direction: int,
) -> Any:
    try:
        segment = document.SketchManager.CreateArc(
            mm_to_sw_m(center_x_mm),
            mm_to_sw_m(center_y_mm),
            0.0,
            mm_to_sw_m(start_x_mm),
            mm_to_sw_m(start_y_mm),
            0.0,
            mm_to_sw_m(end_x_mm),
            mm_to_sw_m(end_y_mm),
            0.0,
            int(direction),
        )
        _require_value(
            segment,
            message="SOLIDWORKS returned no arc segment",
            operation="solidworks.add_arc",
        )
    except ComOperationError:
        raise
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not create the arc",
            operation="solidworks.add_arc",
        ) from exc
    return segment


def finish_sketch(document: Any) -> None:
    try:
        if document.SketchManager.ActiveSketch is not None:
            document.SketchManager.InsertSketch(False)
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not finish the sketch",
            operation="solidworks.finish_sketch",
        ) from exc


def extrude(document: Any, sketch_name: str, depth_mm: float) -> Any:
    depth = mm_to_sw_m(depth_mm)
    try:
        sketch = document.FeatureByName(sketch_name)
        _require_value(
            sketch,
            message="the sketch could not be resolved for extrusion",
            operation="solidworks.extrude",
        )
        _require_selection(
            sketch.Select2(False, 0),
            message="the sketch could not be selected for extrusion",
            operation="solidworks.extrude",
        )
        feature = document.FeatureManager.FeatureExtrusion3(
            True,
            False,
            False,
            0,
            0,
            depth,
            0.0,
            False,
            False,
            False,
            False,
            0.0,
            0.0,
            False,
            False,
            False,
            False,
            True,
            True,
            True,
            0,
            0.0,
            False,
        )
        _require_value(
            feature,
            message="SOLIDWORKS returned no extrusion feature",
            operation="solidworks.extrude",
        )
    except ComOperationError:
        raise
    except Exception as exc:
        raise ComOperationError(
            "SOLIDWORKS could not create the extrusion",
            operation="solidworks.extrude",
        ) from exc
    else:
        return feature


def make_geometry_id() -> str:
    return f"sw-geometry-{uuid4().hex}"


def make_sketch_id() -> str:
    return f"sw-sketch-{uuid4().hex}"


def make_feature_id() -> str:
    return f"sw-feature-{uuid4().hex}"


def _require_selection(
    selected: Any,
    *,
    message: str,
    operation: str,
    details: dict[str, Any] | None = None,
) -> None:
    if not selected:
        raise ComOperationError(message, operation=operation, details=details)


def _require_value(value: Any, *, message: str, operation: str) -> None:
    if not value:
        raise ComOperationError(message, operation=operation)


def _select_plane(document: Any, plane: str) -> None:
    normalized = plane.strip().casefold()
    aliases = {
        "front": 0,
        "front plane": 0,
        "top": 1,
        "top plane": 1,
        "right": 2,
        "right plane": 2,
    }
    feature = None
    if normalized not in aliases:
        try:
            feature = document.FeatureByName(plane)
        except Exception:
            feature = None
    if feature is None:
        planes = []
        current = document.FirstFeature
        while current is not None:
            try:
                if str(current.GetTypeName2) == "RefPlane":
                    planes.append(current)
            except Exception:
                pass
            current = current.GetNextFeature
        try:
            feature = planes[aliases.get(normalized, 0)]
        except (IndexError, KeyError) as exc:
            raise ComOperationError(
                "requested sketch plane could not be resolved",
                operation="solidworks.create_sketch",
                details={"plane": plane},
            ) from exc
    _require_selection(
        feature.Select2(False, 0),
        message="requested sketch plane could not be selected",
        operation="solidworks.create_sketch",
        details={"plane": plane},
    )
