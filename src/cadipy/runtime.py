"""Session-local live document registry and target resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cadipy.backends.executor import DocumentHandle
from cadipy.domain.targets import TargetBinding, resolve_target


class DocumentRegistry:
    """Track serializable document handles for one CADiPy session."""

    def __init__(self) -> None:
        self._documents: dict[str, DocumentHandle] = {}
        self._identity_to_id: dict[tuple[object, ...], str] = {}

    def reconcile(self, handles: Iterable[DocumentHandle]) -> tuple[DocumentHandle, ...]:
        current: dict[str, DocumentHandle] = {}
        identities: dict[tuple[object, ...], str] = {}
        for handle in handles:
            identity = self._identity(handle)
            existing_id = self._identity_to_id.get(identity, handle.id)
            canonical = handle if handle.id == existing_id else self._with_id(handle, existing_id)
            current[canonical.id] = canonical
            identities[identity] = canonical.id
        self._documents = current
        self._identity_to_id = identities
        return tuple(current.values())

    def resolve(self, binding: TargetBinding) -> DocumentHandle:
        resolved = resolve_target(self._documents.values(), binding, mutating=True)
        return resolved

    def get(self, document_id: str) -> DocumentHandle | None:
        return self._documents.get(document_id)

    def clear(self) -> None:
        self._documents.clear()
        self._identity_to_id.clear()

    @staticmethod
    def _identity(handle: DocumentHandle) -> tuple[object, ...]:
        path = None
        if handle.path is not None:
            path = str(Path(handle.path).resolve()).casefold()
        return (
            path,
            handle.document_type,
            handle.title.casefold(),
            handle.configuration.casefold() if handle.configuration else None,
        )

    @staticmethod
    def _with_id(handle: DocumentHandle, document_id: str) -> DocumentHandle:
        return DocumentHandle(
            id=document_id,
            document_type=handle.document_type,
            title=handle.title,
            path=handle.path,
            configuration=handle.configuration,
            active=handle.active,
        )
