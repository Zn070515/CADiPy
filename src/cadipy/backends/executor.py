"""Backend-neutral execution port and serializable result values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from cadipy.domain.documents import DocumentType

if TYPE_CHECKING:
    from pathlib import Path



@dataclass(frozen=True, slots=True)
class ApplicationInfo:
    product: str
    revision: str
    executor: str
    connection_mode: str = "attach"
    owned: bool = False


@dataclass(frozen=True, slots=True)
class DocumentHandle:
    id: str
    document_type: DocumentType
    title: str
    path: Path | None = None
    configuration: str | None = None
    active: bool = False

    kind = "document"


@dataclass(frozen=True, slots=True)
class SketchHandle:
    id: str
    document_id: str
    name: str
    plane: str

    kind = "sketch"


@dataclass(frozen=True, slots=True)
class GeometryHandle:
    id: str
    sketch_id: str
    width_mm: float
    height_mm: float

    kind = "geometry"


@dataclass(frozen=True, slots=True)
class FeatureHandle:
    id: str
    document_id: str
    name: str
    feature_type: str
    depth_mm: float

    kind = "feature"


@dataclass(frozen=True, slots=True)
class RebuildReport:
    success: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SaveReport:
    success: bool
    path: Path
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentInspection:
    document_id: str
    document_type: DocumentType
    path: Path | None
    title: str
    sketch_names: tuple[str, ...] = ()
    feature_names: tuple[str, ...] = ()
    bounding_box_mm: tuple[float, float, float, float, float, float] | None = None
    body_count: int | None = None
    rectangle_width_mm: float | None = None
    rectangle_height_mm: float | None = None
    extrusion_depth_mm: float | None = None
    feature_suppressed: bool | None = None
    rebuild_success: bool | None = None


@runtime_checkable
class SolidWorksExecutor(Protocol):
    """Stable semantic port implemented by Python COM and future C# workers."""

    executor_kind: str

    def attach(self) -> ApplicationInfo: ...

    def launch(self) -> ApplicationInfo: ...

    def connect(self) -> ApplicationInfo: ...

    def application_info(self) -> ApplicationInfo: ...

    def disconnect(self) -> None: ...

    def list_documents(self) -> tuple[DocumentHandle, ...]: ...

    def active_document(self) -> DocumentHandle | None: ...

    def open_document(
        self,
        path: Path,
        document_type: DocumentType = DocumentType.PART,
    ) -> DocumentHandle: ...

    def create_part(self) -> DocumentHandle: ...

    def create_sketch(self, document: DocumentHandle, plane: str) -> SketchHandle: ...

    def add_rectangle(
        self,
        sketch: SketchHandle,
        width_mm: float,
        height_mm: float,
    ) -> GeometryHandle: ...

    def extrude(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        depth_mm: float,
    ) -> FeatureHandle: ...

    def rebuild(self, document: DocumentHandle) -> RebuildReport: ...

    def save(self, document: DocumentHandle, path: Path) -> SaveReport: ...

    def close(self, document: DocumentHandle) -> None: ...

    def reopen(self, path: Path) -> DocumentHandle: ...

    def inspect_document(self, document: DocumentHandle) -> DocumentInspection: ...
