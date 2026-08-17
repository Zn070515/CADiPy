from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from cadipy.domain.sketches import (
    DimensionHandle,
    DimensionType,
    RelationHandle,
    RelationType,
    SketchEntityHandle,
    SketchEntityType,
)


def test_sketch_entity_values_are_serializable_and_use_public_units() -> None:
    entity = SketchEntityHandle(
        id="entity-1",
        document_id="part-1",
        sketch_id="sketch-1",
        entity_type=SketchEntityType.LINE,
        persistent_ref="AQID",
        start_x_mm=-50.0,
        start_y_mm=30.0,
        end_x_mm=50.0,
        end_y_mm=30.0,
    )

    encoded = json.dumps(asdict(entity))

    assert '"entity_type": "line"' in encoded
    assert '"start_x_mm": -50.0' in encoded
    assert "meter" not in encoded
    assert "radian" not in encoded


def test_relation_and_dimension_values_are_explicit() -> None:
    relation = RelationHandle(
        id="relation-1",
        sketch_id="sketch-1",
        relation_type=RelationType.HORIZONTAL,
        entity_ids=("entity-1",),
    )
    dimension = DimensionHandle(
        id="dimension-1",
        sketch_id="sketch-1",
        dimension_type=DimensionType.HORIZONTAL_DISTANCE,
        name="D1@Sketch1",
        value_mm=100.0,
    )

    assert relation.relation_type is RelationType.HORIZONTAL
    assert dimension.dimension_type is DimensionType.HORIZONTAL_DISTANCE
    assert dimension.value_mm == 100.0


def test_enum_values_reject_unknown_contract_values() -> None:
    with pytest.raises(ValueError):
        SketchEntityType("spline")
    with pytest.raises(ValueError):
        RelationType("equal")
    with pytest.raises(ValueError):
        DimensionType("angle")
