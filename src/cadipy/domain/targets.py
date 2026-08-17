"""Explicit target binding and resolve-once selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .errors import (
    AmbiguousSelectionError,
    InvalidArgumentError,
    TargetMismatchError,
    TargetNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from .documents import DocumentType
    from .identities import DocumentIdentity


@dataclass(frozen=True, slots=True)
class TargetBinding:
    document_id: str | None = None
    path: Path | None = None
    title: str | None = None
    document_type: DocumentType | None = None
    configuration: str | None = None

    def __post_init__(self) -> None:
        if not any(
            value is not None
            for value in (
                self.document_id,
                self.path,
                self.title,
                self.document_type,
                self.configuration,
            )
        ):
            raise InvalidArgumentError("target binding must contain at least one criterion")


def _same_path(left: Path | None, right: Path | None) -> bool:
    if left is None or right is None:
        return left is right
    return str(left.resolve()).casefold() == str(right.resolve()).casefold()


def _matches(candidate: DocumentIdentity, binding: TargetBinding) -> bool:
    return all(
        (
            binding.document_id is None or candidate.document_id == binding.document_id,
            binding.path is None or _same_path(candidate.path, binding.path),
            binding.title is None or candidate.title == binding.title,
            binding.document_type is None or candidate.document_type == binding.document_type,
            binding.configuration is None or candidate.configuration == binding.configuration,
        )
    )


def resolve_target(
    candidates: Iterable[DocumentIdentity],
    binding: TargetBinding | None,
    *,
    mutating: bool,
) -> DocumentIdentity:
    """Resolve one stable document identity before a CAD operation executes."""

    items = tuple(candidates)
    if not items:
        raise TargetNotFoundError("no CAD document is available")
    if binding is None:
        if mutating:
            raise TargetNotFoundError("mutating operations require an explicit target binding")
        active = tuple(item for item in items if item.active)
        if len(active) == 1:
            return active[0]
        if len(active) > 1:
            raise AmbiguousSelectionError("more than one active CAD document is available")
        if len(items) == 1:
            return items[0]
        raise TargetNotFoundError("read operation has no unambiguous active target")

    matches = tuple(item for item in items if _matches(item, binding))
    if not matches:
        raise TargetMismatchError("target binding did not match a CAD document")
    if len(matches) > 1:
        raise AmbiguousSelectionError("target binding matched multiple CAD documents")
    return matches[0]
