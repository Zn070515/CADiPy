from __future__ import annotations

from contextlib import suppress

import pytest

from cadipy.domain.sketches import DimensionType, RelationType


def _execute(session, operation: str, *, target=None, params=None) -> dict:
    result = session.execute(operation, target=target, params=params or {})
    assert result.ok is True, result.to_dict()
    assert result.data is not None
    return result.data


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_parametric_sketch_entity_roundtrip_and_dimension_mutation(
    solidworks_session,
    tmp_path,
) -> None:
    document = solidworks_session.create_part()
    reopened = None
    saved_path = tmp_path / "cadipy_parametric_sketch_fixture.SLDPRT"
    try:
        sketch = _execute(
            solidworks_session,
            "sketch.create",
            target=document,
            params={"plane": "Front Plane"},
        )
        entities = _execute(
            solidworks_session,
            "sketch.add_rectangle",
            target=document,
            params={
                "sketch": sketch,
                "width_mm": 100.0,
                "height_mm": 60.0,
                "origin_x_mm": 50.0,
                "origin_y_mm": 30.0,
            },
        )["entities"]
        assert len(entities) == 4
        assert all(entity["persistent_ref"] for entity in entities)

        origin_relation = _execute(
            solidworks_session,
            "sketch.add_relation",
            target=document,
            params={
                "sketch": sketch,
                "relation_type": RelationType.COINCIDENT.value,
                "entities": [entities[0]],
                "anchor_origin": True,
            },
        )
        assert origin_relation["relation_type"] == RelationType.COINCIDENT.value

        relations = tuple(
            _execute(
                solidworks_session,
                "sketch.add_relation",
                target=document,
                params={
                    "sketch": sketch,
                    "relation_type": RelationType.COINCIDENT.value,
                    "entities": [entities[index], entities[(index + 1) % 4]],
                },
            )
            for index in range(4)
        )
        assert len(relations) == 4

        horizontal = _execute(
            solidworks_session,
            "sketch.add_dimension",
            target=document,
            params={
                "sketch": sketch,
                "dimension_type": DimensionType.HORIZONTAL_DISTANCE.value,
                "entities": [entities[0]],
                "value_mm": 100.0,
                "position_x_mm": 0.0,
                "position_y_mm": -40.0,
            },
        )
        vertical = _execute(
            solidworks_session,
            "sketch.add_dimension",
            target=document,
            params={
                "sketch": sketch,
                "dimension_type": DimensionType.VERTICAL_DISTANCE.value,
                "entities": [entities[1]],
                "value_mm": 60.0,
                "position_x_mm": 60.0,
                "position_y_mm": 0.0,
            },
        )
        assert _execute(
            solidworks_session,
            "sketch.inspect_dimension",
            target=document,
            params={"sketch": sketch, "dimension": horizontal},
        )["value_mm"] == pytest.approx(100.0)
        assert _execute(
            solidworks_session,
            "sketch.inspect_dimension",
            target=document,
            params={"sketch": sketch, "dimension": vertical},
        )["value_mm"] == pytest.approx(60.0)

        _execute(
            solidworks_session,
            "part.create_extrude",
            target=document,
            params={"sketch": sketch, "depth_mm": 3.0},
        )
        assert solidworks_session.rebuild(target=document).data["success"] is True
        initial = solidworks_session.inspect(target=document).data
        assert initial is not None
        assert initial["bounding_box_mm"] is not None
        assert initial["rectangle_width_mm"] == pytest.approx(100.0, abs=0.01)
        assert initial["rectangle_height_mm"] == pytest.approx(60.0, abs=0.01)
        assert initial["extrusion_depth_mm"] == pytest.approx(3.0, abs=0.01)

        _execute(
            solidworks_session,
            "document.save",
            target=document,
            params={"path": str(saved_path)},
        )
        assert saved_path.is_file()
        solidworks_session.close(target=document)
        reopened = solidworks_session.open(saved_path)
        reopened_target = {"path": str(saved_path), "document_type": "part"}
        reopened_sketches = _execute(
            solidworks_session,
            "sketch.list",
            target=reopened_target,
        )["sketches"]
        assert len(reopened_sketches) == 1
        reopened_sketch = reopened_sketches[0]
        assert reopened_sketch["document_id"] == reopened.id
        reopened_sketch_inspection = _execute(
            solidworks_session,
            "sketch.inspect",
            target=reopened_target,
            params={"sketch": reopened_sketch},
        )
        assert reopened_sketch_inspection["entity_count"] == 4
        assert reopened_sketch_inspection["dimension_count"] == 2

        entity_inspection = _execute(
            solidworks_session,
            "sketch.inspect_entity",
            target=reopened_target,
            params={"sketch": reopened_sketch, "entity": entities[0]},
        )
        assert entity_inspection["entity_type"] == "line"
        assert _execute(
            solidworks_session,
            "sketch.inspect_dimension",
            target=reopened_target,
            params={"sketch": reopened_sketch, "dimension": horizontal},
        )["value_mm"] == pytest.approx(100.0, abs=0.01)
        assert solidworks_session.rebuild(target=reopened_target).data["success"] is True

        _execute(
            solidworks_session,
            "sketch.set_dimension",
            target=reopened_target,
            params={"sketch": reopened_sketch, "dimension": horizontal, "value_mm": 120.0},
        )
        assert solidworks_session.rebuild(target=reopened_target).data["success"] is True
        final = solidworks_session.inspect(target=reopened_target).data
        assert final is not None
        assert final["bounding_box_mm"] is not None
        assert final["rectangle_width_mm"] == pytest.approx(120.0, abs=0.01)
        assert final["rectangle_height_mm"] == pytest.approx(60.0, abs=0.01)
        assert final["extrusion_depth_mm"] == pytest.approx(3.0, abs=0.01)
    finally:
        if reopened is not None:
            with suppress(Exception):
                solidworks_session.close(target={"path": str(saved_path), "document_type": "part"})
        else:
            with suppress(Exception):
                solidworks_session.close(target=document)
