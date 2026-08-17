from __future__ import annotations

from pathlib import Path

import pytest

from cadipy.backends.executor import DocumentHandle
from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import TargetNotFoundError
from cadipy.domain.targets import TargetBinding
from cadipy.runtime import DocumentRegistry


part_a = DocumentHandle(
    id="backend-a",
    document_type=DocumentType.PART,
    title="PartA",
    path=Path("C:/cad/PartA.SLDPRT"),
)
part_b = DocumentHandle(
    id="backend-b",
    document_type=DocumentType.PART,
    title="PartB",
    path=Path("C:/cad/PartB.SLDPRT"),
)


def test_registry_reuses_identity_and_resolves_target_criteria() -> None:
    registry = DocumentRegistry()

    first = registry.reconcile((part_a, part_b))
    second = registry.reconcile((part_a, part_b))

    assert first[0].id == second[0].id
    assert registry.resolve(TargetBinding(path=part_a.path)) == first[0]
    assert registry.resolve(TargetBinding(title=part_a.title)) == first[0]
    assert registry.resolve(
        TargetBinding(document_type=DocumentType.PART, title=part_a.title)
    ) == first[0]


def test_registry_drops_closed_documents_and_rejects_old_id() -> None:
    registry = DocumentRegistry()
    handle = registry.reconcile((part_a,))[0]

    registry.reconcile(())

    with pytest.raises(TargetNotFoundError):
        registry.resolve(TargetBinding(document_id=handle.id))
