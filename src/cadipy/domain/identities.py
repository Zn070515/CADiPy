"""Stable identity values for CAD documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .errors import InvalidArgumentError

if TYPE_CHECKING:
    from pathlib import Path

    from .documents import DocumentType


@dataclass(frozen=True, slots=True)
class DocumentIdentity:
    """Evidence identifying one document without retaining a COM object."""

    document_id: str
    path: Path | None
    title: str
    document_type: DocumentType
    configuration: str | None = None
    revision: str | None = None
    fingerprint: str | None = None
    active: bool = False

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise InvalidArgumentError("document_id must not be empty")
        if not self.title.strip():
            raise InvalidArgumentError("title must not be empty")
