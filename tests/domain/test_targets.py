from pathlib import Path

import pytest

from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import (
    AmbiguousSelectionError,
    TargetMismatchError,
    TargetNotFoundError,
)
from cadipy.domain.identities import DocumentIdentity
from cadipy.domain.targets import TargetBinding, resolve_target


def _part(*, document_id: str, path: str, active: bool = False) -> DocumentIdentity:
    return DocumentIdentity(
        document_id=document_id,
        path=Path(path),
        title=Path(path).stem,
        document_type=DocumentType.PART,
        active=active,
    )


def test_mutating_operation_requires_explicit_target_binding() -> None:
    with pytest.raises(TargetNotFoundError):
        resolve_target([_part(document_id="part-1", path="A.SLDPRT")], None, mutating=True)


def test_binding_resolves_one_document_by_id_and_path() -> None:
    target = _part(document_id="part-1", path="A.SLDPRT")
    binding = TargetBinding(document_id="part-1", path=Path("A.SLDPRT"))

    assert resolve_target([target], binding, mutating=True) == target


def test_binding_rejects_mismatched_document() -> None:
    target = _part(document_id="part-1", path="A.SLDPRT")

    with pytest.raises(TargetMismatchError):
        resolve_target([target], TargetBinding(document_id="part-2"), mutating=True)


def test_binding_rejects_ambiguous_path_match() -> None:
    candidates = [
        _part(document_id="part-1", path="A.SLDPRT"),
        _part(document_id="part-2", path="A.SLDPRT"),
    ]

    with pytest.raises(AmbiguousSelectionError):
        resolve_target(candidates, TargetBinding(path=Path("A.SLDPRT")), mutating=True)
