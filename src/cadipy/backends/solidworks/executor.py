"""Python COM implementation of the backend-neutral executor port."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cadipy.backends.executor import (
    ApplicationInfo,
    DocumentHandle,
    DocumentInspection,
    FeatureHandle,
    GeometryHandle,
    RebuildReport,
    SaveReport,
    SketchHandle,
)
from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import ComOperationError, DocumentTypeError, RebuildError
from cadipy.domain.units import sw_m_to_mm

from . import application, documents, geometry
from .apartment import ComApartment


class PythonComSolidWorksExecutor:
    """Owns COM objects privately and exposes only CADiPy domain values."""

    executor_kind = "python-com"

    def __init__(self) -> None:
        self._apartment = ComApartment()
        self._application: Any = None
        self._documents: dict[str, Any] = {}
        self._sketches: dict[str, Any] = {}
        self._geometries: dict[str, Any] = {}
        self._features: dict[str, Any] = {}
        self._sketch_documents: dict[str, str] = {}
        self._geometry_sketches: dict[str, str] = {}
        self._feature_documents: dict[str, str] = {}
        self._rebuild_documents: dict[str, bool] = {}
        self._connection_mode = "attach"
        self._owns_application = False

    def __enter__(self) -> Any:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.disconnect()

    def attach(self) -> ApplicationInfo:
        return self._connect(application.attach_application, mode="attach", owned=False)

    def launch(self) -> ApplicationInfo:
        return self._connect(application.launch_application, mode="launch", owned=True)

    def connect(self) -> ApplicationInfo:
        """Backward-compatible alias for strict attach semantics."""

        return self.attach()

    def application_info(self) -> ApplicationInfo:
        self._require_application()
        return self._info()

    def _connect(
        self,
        acquire: Any,
        *,
        mode: str,
        owned: bool,
    ) -> ApplicationInfo:
        if self._application is None:
            self._apartment.__enter__()
            try:
                self._application = acquire()
            except Exception:
                self._apartment.__exit__(None, None, None)
                raise
        self._connection_mode = mode
        self._owns_application = owned
        return self._info()

    def _info(self) -> ApplicationInfo:
        product, revision, executor = application.application_info(
            self._require_application(),
            executor=self.executor_kind,
        )
        return ApplicationInfo(
            product=product,
            revision=revision,
            executor=executor,
            connection_mode=self._connection_mode,
            owned=self._owns_application,
        )

    def disconnect(self) -> None:
        owned = self._owns_application
        app = self._application
        self._features.clear()
        self._geometries.clear()
        self._sketches.clear()
        self._documents.clear()
        self._rebuild_documents.clear()
        self._application = None
        self._owns_application = False
        if owned and app is not None:
            try:
                application.exit_application(app)
            finally:
                self._apartment.__exit__(None, None, None)
        else:
            self._apartment.__exit__(None, None, None)

    def _require_application(self) -> Any:
        if self._application is None:
            raise ComOperationError(
                "connect() must be called before using the SolidWorks executor",
                operation="solidworks.executor",
            )
        return self._application

    def _document_object(self, handle: DocumentHandle) -> Any:
        try:
            return self._documents[handle.id]
        except KeyError as exc:
            raise ComOperationError(
                "document handle is not owned by this executor",
                operation="solidworks.document",
                details={"document_id": handle.id},
            ) from exc

    def create_part(self) -> DocumentHandle:
        document = documents.new_part(self._require_application())
        handle = self._document_handle(document)
        self._documents[handle.id] = document
        return handle

    def list_documents(self) -> tuple[DocumentHandle, ...]:
        live = documents.list_open_documents(self._require_application())
        handles = tuple(self._handle_for_live_document(document) for document in live)
        return handles

    def active_document(self) -> DocumentHandle | None:
        active = documents.active_document(self._require_application())
        if active is None:
            return None
        return self._handle_for_live_document(active, active=True)

    def open_document(
        self,
        path: Path,
        document_type: DocumentType = DocumentType.PART,
    ) -> DocumentHandle:
        document = documents.open_document(self._require_application(), path, document_type)
        handle = self._document_handle(document, path=path)
        self._documents[handle.id] = document
        return handle

    def create_sketch(self, document: DocumentHandle, plane: str) -> SketchHandle:
        model = self._document_object(document)
        sketch = geometry.create_sketch(model, plane)
        sketch_id = geometry.make_sketch_id()
        name = str(getattr(sketch, "Name", "Sketch1"))
        handle = SketchHandle(id=sketch_id, document_id=document.id, name=name, plane=plane)
        self._sketches[sketch_id] = model
        self._sketch_documents[sketch_id] = document.id
        return handle

    def add_rectangle(
        self,
        sketch: SketchHandle,
        width_mm: float,
        height_mm: float,
    ) -> GeometryHandle:
        try:
            document_id = self._sketch_documents[sketch.id]
        except KeyError as exc:
            raise ComOperationError(
                "sketch handle is not owned by this executor",
                operation="solidworks.add_rectangle",
            ) from exc
        document = self._document_object_by_id(document_id)
        rectangle = geometry.add_rectangle(document, width_mm, height_mm)
        geometry_id = geometry.make_geometry_id()
        handle = GeometryHandle(
            id=geometry_id,
            sketch_id=sketch.id,
            width_mm=width_mm,
            height_mm=height_mm,
        )
        self._geometries[geometry_id] = rectangle
        self._geometry_sketches[geometry_id] = sketch.id
        return handle

    def extrude(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        depth_mm: float,
    ) -> FeatureHandle:
        model = self._document_object(document)
        feature = geometry.extrude(model, sketch.name, depth_mm)
        feature_id = geometry.make_feature_id()
        name = str(getattr(feature, "Name", "Boss-Extrude1"))
        handle = FeatureHandle(
            id=feature_id,
            document_id=document.id,
            name=name,
            feature_type="extrusion",
            depth_mm=depth_mm,
        )
        self._features[feature_id] = feature
        self._feature_documents[feature_id] = document.id
        return handle

    def rebuild(self, document: DocumentHandle) -> RebuildReport:
        try:
            success = bool(self._document_object(document).ForceRebuild3(True))
        except Exception as exc:
            raise RebuildError(
                "SOLIDWORKS rebuild call failed",
                operation="solidworks.rebuild",
                details={"document_id": document.id},
            ) from exc
        if not success:
            raise RebuildError(
                "SOLIDWORKS rebuild did not succeed",
                operation="solidworks.rebuild",
                details={"document_id": document.id},
            )
        self._rebuild_documents[document.id] = True
        return RebuildReport(success=True)

    def save(self, document: DocumentHandle, path: Path) -> SaveReport:
        model = self._document_object(document)
        try:
            import pythoncom
            from win32com.client import VARIANT

            errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)

            success = bool(
                model.Extension.SaveAs2(
                    str(path),
                    documents.SW_SAVE_CURRENT_VERSION,
                    documents.SW_SAVE_SILENT,
                    pythoncom.Nothing,
                    "",
                    False,
                    errors,
                    warnings,
                )
            )
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS could not save the document",
                operation="solidworks.save",
                details={"document_id": document.id, "path": str(path)},
            ) from exc
        if not success:
            raise ComOperationError(
                "SOLIDWORKS returned a failed save status",
                operation="solidworks.save",
                details={"document_id": document.id, "path": str(path)},
            )
        return SaveReport(success=True, path=path)

    def close(self, document: DocumentHandle) -> None:
        documents.close_document(self._require_application(), self._document_object(document))
        self._documents.pop(document.id, None)
        self._rebuild_documents.pop(document.id, None)

    def reopen(self, path: Path) -> DocumentHandle:
        return self.open_document(path)

    def inspect_document(self, document: DocumentHandle) -> DocumentInspection:
        model = self._document_object(document)
        try:
            doc_type = documents.document_type(model)
            title = str(model.GetTitle)
            raw_path = str(model.GetPathName)
            path = Path(raw_path) if raw_path else document.path
            feature_names: list[str] = []
            sketch_names: list[str] = []
            feature_suppressed = None
            feature = model.FirstFeature
            while feature is not None:
                feature_names.append(str(feature.Name))
                feature_type = str(feature.GetTypeName2)
                if feature_type == "ProfileFeature":
                    sketch_names.append(str(feature.Name))
                if feature_type == "Extrusion":
                    feature_suppressed = bool(feature.IsSuppressed)
                feature = feature.GetNextFeature
            body_count = None
            try:
                bodies = model.GetBodies2(0, True)
                body_count = len(bodies) if bodies is not None else 0
            except Exception:
                pass
            bounding_box_mm = None
            rectangle_width_mm = None
            rectangle_height_mm = None
            extrusion_depth_mm = None
            if doc_type is DocumentType.PART:
                try:
                    raw_box = tuple(float(value) for value in model.GetPartBox(True))
                    if len(raw_box) == 6:
                        bounding_box_mm = (
                            sw_m_to_mm(raw_box[0]),
                            sw_m_to_mm(raw_box[1]),
                            sw_m_to_mm(raw_box[2]),
                            sw_m_to_mm(raw_box[3]),
                            sw_m_to_mm(raw_box[4]),
                            sw_m_to_mm(raw_box[5]),
                        )
                        extents = sorted(
                            abs(bounding_box_mm[index + 3] - bounding_box_mm[index])
                            for index in range(3)
                        )
                        extrusion_depth_mm = extents[0]
                        rectangle_height_mm = extents[1]
                        rectangle_width_mm = extents[2]
                except Exception:
                    pass
        except DocumentTypeError:
            raise
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS document inspection failed",
                operation="solidworks.inspect_document",
                details={"document_id": document.id},
            ) from exc
        return DocumentInspection(
            document_id=document.id,
            document_type=doc_type,
            path=path,
            title=title,
            sketch_names=tuple(sketch_names),
            feature_names=tuple(feature_names),
            body_count=body_count,
            bounding_box_mm=bounding_box_mm,
            rectangle_width_mm=rectangle_width_mm,
            rectangle_height_mm=rectangle_height_mm,
            extrusion_depth_mm=extrusion_depth_mm,
            feature_suppressed=feature_suppressed,
            rebuild_success=self._rebuild_documents.get(document.id),
        )

    def _document_handle(self, document: Any, *, path: Path | None = None) -> DocumentHandle:
        try:
            doc_type = documents.document_type(document)
            title = str(document.GetTitle)
            raw_path = str(document.GetPathName)
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS document identity could not be read",
                operation="solidworks.document",
            ) from exc
        return DocumentHandle(
            id=documents.make_document_id(),
            document_type=doc_type,
            title=title,
            path=path or (Path(raw_path) if raw_path else None),
        )

    def _handle_for_live_document(self, document: Any, *, active: bool = False) -> DocumentHandle:
        for document_id, known in self._documents.items():
            if self._same_document(known, document):
                return DocumentHandle(
                    id=document_id,
                    document_type=documents.document_type(document),
                    title=str(document.GetTitle),
                    path=Path(str(document.GetPathName))
                    if str(document.GetPathName)
                    else known.path,
                    configuration=known.configuration,
                    active=active,
                )
        handle = self._document_handle(document)
        handle = DocumentHandle(
            id=handle.id,
            document_type=handle.document_type,
            title=handle.title,
            path=handle.path,
            configuration=handle.configuration,
            active=active,
        )
        self._documents[handle.id] = document
        return handle

    @staticmethod
    def _same_document(left: Any, right: Any) -> bool:
        try:
            return left is right or left.GetPathName == right.GetPathName and left.GetTitle == right.GetTitle
        except Exception:
            return False

    def _document_object_by_id(self, document_id: str) -> Any:
        try:
            return self._documents[document_id]
        except KeyError as exc:
            raise ComOperationError(
                "document handle is not owned by this executor",
                operation="solidworks.document",
                details={"document_id": document_id},
            ) from exc
