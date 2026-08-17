from __future__ import annotations

from contextlib import suppress

import pytest

from cadipy.domain.sketches import DimensionType, RelationType


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_parametric_sketch_entity_roundtrip_and_dimension_mutation(
    solidworks_executor,
    tmp_path,
) -> None:
    document = solidworks_executor.create_part()
    reopened = None
    saved_path = tmp_path / "cadipy_parametric_sketch_fixture.SLDPRT"
    try:
        sketch = solidworks_executor.create_sketch(document, "Front Plane")
        entities = solidworks_executor.add_sketch_rectangle(
            document, sketch, 100.0, 60.0, origin_x_mm=50.0, origin_y_mm=30.0
        )
        assert len(entities) == 4
        assert all(entity.persistent_ref for entity in entities)

        origin_relation = solidworks_executor.add_relation(
            document,
            sketch,
            RelationType.COINCIDENT,
            (entities[0],),
            anchor_origin=True,
        )
        assert origin_relation.relation_type is RelationType.COINCIDENT

        relations = tuple(
            solidworks_executor.add_relation(
                document,
                sketch,
                RelationType.COINCIDENT,
                (entities[index], entities[(index + 1) % 4]),
            )
            for index in range(4)
        )
        assert len(relations) == 4

        horizontal = solidworks_executor.add_dimension(
            document,
            sketch,
            DimensionType.HORIZONTAL_DISTANCE,
            (entities[0],),
            100.0,
            0.0,
            -40.0,
        )
        vertical = solidworks_executor.add_dimension(
            document,
            sketch,
            DimensionType.VERTICAL_DISTANCE,
            (entities[1],),
            60.0,
            60.0,
            0.0,
        )
        assert solidworks_executor.inspect_dimension(
            document, sketch, horizontal
        ).value_mm == pytest.approx(100.0)
        assert solidworks_executor.inspect_dimension(
            document, sketch, vertical
        ).value_mm == pytest.approx(60.0)

        solidworks_executor.extrude(document, sketch, 3.0)
        assert solidworks_executor.rebuild(document).success is True
        initial = solidworks_executor.inspect_document(document)
        assert initial.bounding_box_mm is not None
        assert initial.rectangle_width_mm == pytest.approx(100.0, abs=0.01)
        assert initial.rectangle_height_mm == pytest.approx(60.0, abs=0.01)
        assert initial.extrusion_depth_mm == pytest.approx(3.0, abs=0.01)

        assert solidworks_executor.save(document, saved_path).success is True
        solidworks_executor.close(document)
        reopened = solidworks_executor.open_document(saved_path)
        reopened_sketches = solidworks_executor.list_sketches(reopened)
        assert len(reopened_sketches) == 1
        reopened_sketch = reopened_sketches[0]
        assert reopened_sketch.document_id == reopened.id
        reopened_sketch_inspection = solidworks_executor.inspect_sketch(reopened, reopened_sketch)
        assert reopened_sketch_inspection.entity_count == 4
        assert reopened_sketch_inspection.dimension_count == 2

        entity_inspection = solidworks_executor.inspect_entity(
            reopened,
            reopened_sketch,
            entities[0],
        )
        assert entity_inspection.entity_type.value == "line"
        assert solidworks_executor.inspect_dimension(
            reopened, reopened_sketch, horizontal
        ).value_mm == pytest.approx(100.0, abs=0.01)
        assert solidworks_executor.rebuild(reopened).success is True

        solidworks_executor.set_dimension(reopened, reopened_sketch, horizontal, 120.0)
        assert solidworks_executor.rebuild(reopened).success is True
        final = solidworks_executor.inspect_document(reopened)
        assert final.bounding_box_mm is not None
        assert final.rectangle_width_mm == pytest.approx(120.0, abs=0.01)
        assert final.rectangle_height_mm == pytest.approx(60.0, abs=0.01)
        assert final.extrusion_depth_mm == pytest.approx(3.0, abs=0.01)
    finally:
        if reopened is not None:
            with suppress(Exception):
                solidworks_executor.close(reopened)
        else:
            with suppress(Exception):
                solidworks_executor.close(document)
