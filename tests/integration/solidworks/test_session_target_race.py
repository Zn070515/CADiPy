from __future__ import annotations

import pytest


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_explicit_target_survives_active_document_change(solidworks_session) -> None:
    part_a = solidworks_session.create_part()
    part_b = solidworks_session.create_part()

    active = solidworks_session.active_document()
    assert active is not None
    assert active.id == part_b.id

    rebuilt = solidworks_session.rebuild(target=part_a)
    inspected = solidworks_session.inspect(target=part_a)

    assert rebuilt.data["success"] is True
    assert inspected.data["document_id"] == part_a.id
