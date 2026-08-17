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
from cadipy.domain.errors import (
    ComOperationError,
    DocumentTypeError,
    EntityReferenceInvalidError,
    RebuildError,
)
from cadipy.domain.sketches import (
    DimensionHandle,
    DimensionInspection,
    DimensionType,
    RelationHandle,
    RelationType,
    SketchEntityHandle,
    SketchEntityInspection,
    SketchEntityType,
    SketchInspection,
)
from cadipy.domain.units import mm_to_sw_m, sw_m_to_mm

from . import application, documents, geometry
from .apartment import ComApartment
from .constants import SW_INPUT_DIM_VAL_ON_CREATE
from .persistence import encode_persist_reference, resolve_persist_reference

_RELATION_CODES = {
    RelationType.HORIZONTAL: "sgHORIZONTAL2D",
    RelationType.VERTICAL: "sgVERTICAL2D",
    RelationType.COINCIDENT: "sgCOINCIDENT",
    RelationType.PARALLEL: "sgPARALLEL",
    RelationType.PERPENDICULAR: "sgPERPENDICULAR",
    RelationType.TANGENT: "sgTANGENT",
    RelationType.CONCENTRIC: "sgCONCENTRIC",
}

_RELATION_METHODS = {
    RelationType.HORIZONTAL: "SketchConstrainHorizontal",
    RelationType.VERTICAL: "SketchConstrainVertical",
    RelationType.COINCIDENT: "SketchConstrainCoincident",
    RelationType.PARALLEL: "SketchConstrainParallel",
    RelationType.PERPENDICULAR: "SketchConstrainPerp",
    RelationType.TANGENT: "SketchConstrainTangent",
    RelationType.CONCENTRIC: "SketchConstrainConcentric",
}

_SKETCH_POINT_TOLERANCE_MM = 1e-6


class PythonComSolidWorksExecutor:
    """Owns COM objects privately and exposes only CADiPy domain values."""

    executor_kind = "python-com"

    def __init__(self) -> None:
        self._apartment = ComApartment()
        self._application: Any = None
        self._documents: dict[str, Any] = {}
        self._document_handles: dict[str, DocumentHandle] = {}
        self._sketches: dict[str, Any] = {}
        self._sketch_handles: dict[str, SketchHandle] = {}
        self._geometries: dict[str, Any] = {}
        self._entity_handles: dict[str, SketchEntityHandle] = {}
        self._entity_documents: dict[str, str] = {}
        self._entity_sketches: dict[str, str] = {}
        self._features: dict[str, Any] = {}
        self._relation_handles: dict[str, RelationHandle] = {}
        self._dimension_handles: dict[str, DimensionHandle] = {}
        self._dimension_objects: dict[str, Any] = {}
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

    def attach(self, *, visible: bool | None = None) -> ApplicationInfo:
        return self._connect(
            application.attach_application,
            mode="attach",
            owned=False,
            visible=visible,
        )

    def launch(self, *, visible: bool = True) -> ApplicationInfo:
        return self._connect(
            application.launch_application,
            mode="launch",
            owned=True,
            visible=visible,
        )

    def connect(self) -> ApplicationInfo:
        """Backward-compatible alias for strict attach semantics."""

        return self.attach()

    def set_visibility(self, visible: bool) -> ApplicationInfo:
        app = self._require_application()
        application.set_visibility(app, visible)
        return self._info()

    def application_info(self) -> ApplicationInfo:
        self._require_application()
        return self._info()

    def _connect(
        self,
        acquire: Any,
        *,
        mode: str,
        owned: bool,
        visible: bool | None,
    ) -> ApplicationInfo:
        if self._application is None:
            self._apartment.__enter__()
            try:
                self._application = acquire()
            except Exception:
                self._apartment.__exit__(None, None, None)
                raise
            if visible is not None:
                application.set_visibility(self._application, visible)
        self._connection_mode = mode
        self._owns_application = owned
        return self._info()

    def _info(self) -> ApplicationInfo:
        product, revision, executor, visible = application.application_info(
            self._require_application(),
            executor=self.executor_kind,
        )
        return ApplicationInfo(
            product=product,
            revision=revision,
            executor=executor,
            connection_mode=self._connection_mode,
            owned=self._owns_application,
            visible=visible,
        )

    def disconnect(self) -> None:
        owned = self._owns_application
        app = self._application
        self._features.clear()
        self._geometries.clear()
        self._entity_handles.clear()
        self._entity_documents.clear()
        self._entity_sketches.clear()
        self._relation_handles.clear()
        self._dimension_handles.clear()
        self._dimension_objects.clear()
        self._sketches.clear()
        self._sketch_handles.clear()
        self._documents.clear()
        self._document_handles.clear()
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
        self._document_handles[handle.id] = handle
        return handle

    def list_documents(self) -> tuple[DocumentHandle, ...]:
        live = documents.list_open_documents(self._require_application())
        return tuple(self._handle_for_live_document(document) for document in live)

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
        self._document_handles[handle.id] = handle
        return handle

    def create_sketch(self, document: DocumentHandle, plane: str) -> SketchHandle:
        model = self._document_object(document)
        sketch = geometry.create_sketch(model, plane)
        sketch_id = geometry.make_sketch_id()
        name = str(getattr(sketch, "Name", "Sketch1"))
        persistent_ref = self._persistent_ref(model, sketch)
        handle = SketchHandle(
            id=sketch_id,
            document_id=document.id,
            name=name,
            plane=plane,
            persistent_ref=persistent_ref,
        )
        self._sketches[sketch_id] = model
        self._sketch_handles[sketch_id] = handle
        self._sketch_documents[sketch_id] = document.id
        return handle

    def list_sketches(self, document: DocumentHandle) -> tuple[SketchHandle, ...]:
        model = self._document_object(document)
        result: list[SketchHandle] = []
        feature = model.FirstFeature
        while feature is not None:
            if str(feature.GetTypeName2) == "ProfileFeature":
                name = str(feature.Name)
                existing = next(
                    (
                        item
                        for item in self._sketch_handles.values()
                        if item.name == name and item.document_id == document.id
                    ),
                    None,
                )
                handle = existing or SketchHandle(
                    id=geometry.make_sketch_id(),
                    document_id=document.id,
                    name=name,
                    plane="unknown",
                    persistent_ref=self._persistent_ref(model, feature),
                )
                self._sketch_handles[handle.id] = handle
                self._sketches[handle.id] = model
                self._sketch_documents[handle.id] = document.id
                result.append(handle)
            feature = feature.GetNextFeature
        return tuple(result)

    def inspect_sketch(self, document: DocumentHandle, sketch: SketchHandle) -> SketchInspection:
        model = self._document_object(document)
        sketch_feature = self._resolve_sketch(model, sketch)
        sketch_object = self._active_sketch_object(model, sketch, sketch_feature)
        try:
            segments = tuple(_com_collection(sketch_object, "GetSketchSegments"))
            relation_count = sum(
                len(_com_collection(segment, "GetConstraints")) for segment in segments
            )
            fully_defined = None
            if hasattr(sketch_object, "IsFullyDefined"):
                fully_defined = bool(sketch_object.IsFullyDefined())
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS could not inspect the sketch",
                operation="solidworks.inspect_sketch",
            ) from exc
        dimension_count = sum(
            1
            for item in self._dimension_handles.values()
            if item.name.endswith(f"@{sketch.name}") and _parameter_exists(model, item.name)
        )
        return SketchInspection(
            sketch_id=sketch.id,
            name=str(sketch_feature.Name),
            plane=sketch.plane,
            entity_count=len(segments),
            relation_count=relation_count,
            dimension_count=dimension_count,
            fully_defined=fully_defined,
        )

    def add_line(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        start_x_mm: float,
        start_y_mm: float,
        end_x_mm: float,
        end_y_mm: float,
    ) -> SketchEntityHandle:
        model = self._document_object(document)
        self._activate_sketch(model, sketch)
        segment = geometry.add_line(model, start_x_mm, start_y_mm, end_x_mm, end_y_mm)
        return self._register_entity(
            document,
            sketch,
            segment,
            SketchEntityType.LINE,
            start_x_mm=start_x_mm,
            start_y_mm=start_y_mm,
            end_x_mm=end_x_mm,
            end_y_mm=end_y_mm,
        )

    def add_sketch_rectangle(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        width_mm: float,
        height_mm: float,
        origin_x_mm: float = 0.0,
        origin_y_mm: float = 0.0,
    ) -> tuple[SketchEntityHandle, ...]:
        half_width = width_mm / 2.0
        half_height = height_mm / 2.0
        points = (
            (origin_x_mm - half_width, origin_y_mm - half_height),
            (origin_x_mm + half_width, origin_y_mm - half_height),
            (origin_x_mm + half_width, origin_y_mm + half_height),
            (origin_x_mm - half_width, origin_y_mm + half_height),
        )
        starts = points
        entities = [
            self.add_line(
                document,
                sketch,
                start_x_mm=starts[index][0],
                start_y_mm=starts[index][1],
                end_x_mm=points[(index + 1) % 4][0],
                end_y_mm=points[(index + 1) % 4][1],
            )
            for index in range(4)
        ]
        return tuple(entities)

    def add_circle(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        center_x_mm: float,
        center_y_mm: float,
        radius_mm: float,
    ) -> SketchEntityHandle:
        model = self._document_object(document)
        self._activate_sketch(model, sketch)
        segment = geometry.add_circle(model, center_x_mm, center_y_mm, radius_mm)
        return self._register_entity(
            document,
            sketch,
            segment,
            SketchEntityType.CIRCLE,
            center_x_mm=center_x_mm,
            center_y_mm=center_y_mm,
            radius_mm=radius_mm,
        )

    def add_arc(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        center_x_mm: float,
        center_y_mm: float,
        start_x_mm: float,
        start_y_mm: float,
        end_x_mm: float,
        end_y_mm: float,
        direction: int = 1,
    ) -> SketchEntityHandle:
        model = self._document_object(document)
        self._activate_sketch(model, sketch)
        segment = geometry.add_arc(
            model,
            center_x_mm,
            center_y_mm,
            start_x_mm,
            start_y_mm,
            end_x_mm,
            end_y_mm,
            direction,
        )
        return self._register_entity(
            document,
            sketch,
            segment,
            SketchEntityType.ARC,
            start_x_mm=start_x_mm,
            start_y_mm=start_y_mm,
            end_x_mm=end_x_mm,
            end_y_mm=end_y_mm,
            center_x_mm=center_x_mm,
            center_y_mm=center_y_mm,
        )

    def add_relation(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        relation_type: RelationType,
        entities: tuple[SketchEntityHandle, ...],
        anchor_origin: bool = False,
    ) -> RelationHandle:
        model = self._document_object(document)
        self._activate_sketch(model, sketch)
        objects = self._resolve_entities(model, sketch, entities)
        before_constraints = tuple(
            constraint for obj in objects for constraint in _com_collection(obj, "GetConstraints")
        )
        before = len(before_constraints)
        relation_code = _RELATION_CODES[relation_type]
        if anchor_origin:
            if relation_type is not RelationType.COINCIDENT or len(entities) != 1:
                raise ComOperationError(
                    "origin anchoring requires one entity and a coincident relation",
                    operation="solidworks.add_relation",
                )
            self._select_origin_endpoint(model, entities[0], objects[0])
            try:
                getattr(model, _RELATION_METHODS[relation_type])()
            except Exception as exc:
                raise ComOperationError(
                    "SOLIDWORKS rejected the origin anchor relation",
                    operation="solidworks.add_relation",
                ) from exc
            finally:
                model.ClearSelection2(True)
            return self._new_relation_handle(sketch, relation_type, entities)
        if relation_code in before_constraints:
            return self._new_relation_handle(sketch, relation_type, entities)
        if relation_type is RelationType.COINCIDENT and _has_exact_shared_endpoint(entities):
            # SOLIDWORKS treats independently-created endpoints at exactly the
            # same coordinates as an already-satisfied geometric coincidence
            # and does not add a duplicate sgCOINCIDENT relation.
            return self._new_relation_handle(sketch, relation_type, entities)
        if relation_type is RelationType.COINCIDENT and len(entities) == 2:
            self._select_coincident_endpoints(model, entities, objects)
        else:
            self._select_objects(model, objects)
        try:
            getattr(model, _RELATION_METHODS[relation_type])()
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS rejected the sketch relation",
                operation="solidworks.add_relation",
                details={"relation_type": relation_type.value},
            ) from exc
        finally:
            model.ClearSelection2(True)
        after_constraints = tuple(
            constraint for obj in objects for constraint in _com_collection(obj, "GetConstraints")
        )
        after = len(after_constraints)
        if after <= before and relation_code not in after_constraints:
            raise ComOperationError(
                "SOLIDWORKS did not create the requested sketch relation",
                operation="solidworks.add_relation",
                details={"relation_type": relation_type.value},
            )
        return self._new_relation_handle(sketch, relation_type, entities)

    def _new_relation_handle(
        self,
        sketch: SketchHandle,
        relation_type: RelationType,
        entities: tuple[SketchEntityHandle, ...],
    ) -> RelationHandle:
        handle = RelationHandle(
            id=f"sw-relation-{geometry.make_geometry_id().removeprefix('sw-geometry-')}",
            sketch_id=sketch.id,
            relation_type=relation_type,
            entity_ids=tuple(item.id for item in entities),
        )
        self._relation_handles[handle.id] = handle
        return handle

    def add_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension_type: DimensionType,
        entities: tuple[SketchEntityHandle, ...],
        value_mm: float,
        position_x_mm: float,
        position_y_mm: float,
    ) -> DimensionHandle:
        model = self._document_object(document)
        self._activate_sketch(model, sketch)
        objects = self._resolve_entities(model, sketch, entities)
        self._select_objects(model, objects)
        try:
            display = self._add_dimension_without_prompt(
                model, dimension_type, position_x_mm, position_y_mm
            )
            if display is None:
                raise ComOperationError(  # noqa: TRY301
                    "SOLIDWORKS returned no sketch dimension",
                    operation="solidworks.add_dimension",
                )
            dimension_object = display.GetDimension2(0)
            name = str(_com_value(dimension_object, "GetNameForSelection"))
            set_status = dimension_object.SetSystemValue3(mm_to_sw_m(value_mm), 0, "")
            if set_status not in (0, None):
                raise ComOperationError(  # noqa: TRY301
                    "SOLIDWORKS rejected the sketch dimension value",
                    operation="solidworks.add_dimension",
                    details={"status": set_status},
                )
        except ComOperationError:
            raise
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS could not create the sketch dimension",
                operation="solidworks.add_dimension",
            ) from exc
        finally:
            model.ClearSelection2(True)
        return self._register_dimension(
            sketch,
            dimension_object,
            dimension_type,
            name,
            value_mm,
        )

    def set_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension: DimensionHandle,
        value_mm: float,
    ) -> DimensionHandle:
        model = self._document_object(document)
        self._activate_sketch(model, sketch)
        dimension_object = self._resolve_dimension(model, sketch, dimension)
        try:
            status = dimension_object.SetSystemValue3(mm_to_sw_m(value_mm), 0, "")
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS could not set the sketch dimension",
                operation="solidworks.set_dimension",
            ) from exc
        if status not in (0, None):
            raise ComOperationError(
                "SOLIDWORKS rejected the sketch dimension update",
                operation="solidworks.set_dimension",
                details={"status": status},
            )
        updated = DimensionHandle(
            id=dimension.id,
            sketch_id=dimension.sketch_id,
            dimension_type=dimension.dimension_type,
            name=dimension.name,
            value_mm=value_mm,
            persistent_ref=dimension.persistent_ref,
        )
        self._dimension_handles[dimension.id] = updated
        return updated

    def inspect_entity(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        entity: SketchEntityHandle,
    ) -> SketchEntityInspection:
        model = self._document_object(document)
        resolved = self._resolve_entity(model, sketch, entity)
        try:
            relation_count = len(_com_collection(resolved, "GetConstraints"))
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS could not inspect the sketch entity",
                operation="solidworks.inspect_entity",
            ) from exc
        return SketchEntityInspection(
            handle=entity,
            entity_type=entity.entity_type,
            relation_count=relation_count,
        )

    def inspect_dimension(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        dimension: DimensionHandle,
    ) -> DimensionInspection:
        model = self._document_object(document)
        dimension_object = self._resolve_dimension(model, sketch, dimension)
        try:
            raw_value = dimension_object.SystemValue
            value_mm = sw_m_to_mm(float(raw_value))
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS could not inspect the sketch dimension",
                operation="solidworks.inspect_dimension",
            ) from exc
        updated = DimensionHandle(
            id=dimension.id,
            sketch_id=dimension.sketch_id,
            dimension_type=dimension.dimension_type,
            name=dimension.name,
            value_mm=value_mm,
            persistent_ref=dimension.persistent_ref,
        )
        self._dimension_handles[dimension.id] = updated
        return DimensionInspection(handle=updated, value_mm=value_mm)

    def _add_dimension_without_prompt(
        self,
        model: Any,
        dimension_type: DimensionType,
        position_x_mm: float,
        position_y_mm: float,
    ) -> Any:
        app = self._require_application()
        previous = bool(app.GetUserPreferenceToggle(SW_INPUT_DIM_VAL_ON_CREATE))
        if previous:
            app.SetUserPreferenceToggle(SW_INPUT_DIM_VAL_ON_CREATE, False)
        try:
            return _add_dimension(model, dimension_type, position_x_mm, position_y_mm)
        finally:
            if previous:
                app.SetUserPreferenceToggle(SW_INPUT_DIM_VAL_ON_CREATE, True)

    def _register_entity(
        self,
        document: DocumentHandle,
        sketch: SketchHandle,
        segment: Any,
        entity_type: SketchEntityType,
        **geometry_values: float,
    ) -> SketchEntityHandle:
        handle = SketchEntityHandle(
            id=f"sw-entity-{geometry.make_geometry_id().removeprefix('sw-geometry-')}",
            document_id=document.id,
            sketch_id=sketch.id,
            entity_type=entity_type,
            persistent_ref=self._persistent_ref(self._document_object(document), segment),
            sketch_persistent_ref=sketch.persistent_ref,
            **geometry_values,
        )
        self._entity_handles[handle.id] = handle
        self._entity_documents[handle.id] = document.id
        self._entity_sketches[handle.id] = sketch.id
        self._geometries[handle.id] = segment
        self._geometry_sketches[handle.id] = sketch.id
        return handle

    def _register_dimension(
        self,
        sketch: SketchHandle,
        dimension_object: Any,
        dimension_type: DimensionType,
        name: str,
        value_mm: float,
    ) -> DimensionHandle:
        try:
            persistent_ref = self._persistent_ref_from_object(
                dimension_object,
                self._document_for_sketch_id(sketch.id),
            )
        except EntityReferenceInvalidError:
            # SOLIDWORKS 2026 does not expose a usable persistent reference for
            # IDimension here; the validated Dn@SketchName parameter is the
            # explicit dimension identity at the public boundary.
            persistent_ref = None
        handle = DimensionHandle(
            id=f"sw-dimension-{geometry.make_geometry_id().removeprefix('sw-geometry-')}",
            sketch_id=sketch.id,
            dimension_type=dimension_type,
            name=name,
            value_mm=value_mm,
            persistent_ref=persistent_ref,
        )
        self._dimension_handles[handle.id] = handle
        self._dimension_objects[handle.id] = dimension_object
        return handle

    def _document_for_sketch_id(self, sketch_id: str) -> DocumentHandle:
        try:
            return self._document_handles[self._sketch_documents[sketch_id]]
        except KeyError as exc:
            raise EntityReferenceInvalidError(
                "sketch handle is not resolvable in this session",
                operation="solidworks.sketch",
                details={"sketch_id": sketch_id},
            ) from exc

    def _persistent_ref(self, model: Any, obj: Any) -> str:
        try:
            return encode_persist_reference(model.Extension.GetPersistReference3(obj))
        except EntityReferenceInvalidError:
            raise
        except Exception as exc:
            raise EntityReferenceInvalidError(
                "SOLIDWORKS did not provide a persistent reference",
                operation="solidworks.persistent_reference.create",
            ) from exc

    def _persistent_ref_from_object(self, obj: Any, document: DocumentHandle) -> str:
        return self._persistent_ref(self._document_object(document), obj)

    def _resolve_sketch(self, model: Any, sketch: SketchHandle) -> Any:
        if not sketch.persistent_ref:
            raise EntityReferenceInvalidError(
                "sketch handle has no persistent reference",
                operation="solidworks.sketch.resolve",
                details={"sketch_id": sketch.id},
            )
        feature = resolve_persist_reference(model.Extension, sketch.persistent_ref)
        if str(getattr(feature, "Name", "")) != sketch.name:
            raise EntityReferenceInvalidError(
                "persistent reference does not identify the requested sketch",
                operation="solidworks.sketch.resolve",
                details={"sketch_id": sketch.id, "sketch_name": sketch.name},
            )
        return feature

    @staticmethod
    def _specific_sketch(feature: Any) -> Any:
        try:
            sketch_segments = feature.GetSketchSegments
        except Exception:
            sketch_segments = None
        if sketch_segments is not None:
            return feature
        try:
            sketch = feature.GetSpecificFeature2()
        except Exception as exc:
            raise ComOperationError(
                "SOLIDWORKS did not expose the sketch object",
                operation="solidworks.sketch",
            ) from exc
        if sketch is None:
            raise ComOperationError(
                "SOLIDWORKS returned no sketch object",
                operation="solidworks.sketch",
            )
        return sketch

    def _active_sketch_object(
        self,
        model: Any,
        sketch: SketchHandle,
        feature: Any,
    ) -> Any:
        active = getattr(model.SketchManager, "ActiveSketch", None)
        if active is None or str(getattr(active, "Name", "")) != sketch.name:
            self._activate_sketch(model, sketch)
            active = getattr(model.SketchManager, "ActiveSketch", None)
        if active is not None:
            return active
        return self._specific_sketch(feature)

    def _activate_sketch(self, model: Any, sketch: SketchHandle) -> Any:
        feature = self._resolve_sketch(model, sketch)
        active = getattr(model.SketchManager, "ActiveSketch", None)
        if active is None or str(getattr(active, "Name", "")) != str(sketch.name):
            try:
                model.ClearSelection2(True)
                if not feature.Select2(False, 0):
                    raise ComOperationError(  # noqa: TRY301
                        "sketch could not be selected for editing",
                        operation="solidworks.sketch.activate",
                    )
                model.EditSketch()
            except ComOperationError:
                raise
            except Exception as exc:
                raise ComOperationError(
                    "SOLIDWORKS could not activate the sketch",
                    operation="solidworks.sketch.activate",
                ) from exc
        return feature

    def _resolve_entity(
        self,
        model: Any,
        sketch: SketchHandle,
        entity: SketchEntityHandle,
    ) -> Any:
        if not entity.persistent_ref:
            raise EntityReferenceInvalidError(
                "sketch entity has no persistent reference",
                operation="solidworks.entity.resolve",
                details={"entity_id": entity.id},
            )
        if (
            entity.sketch_persistent_ref
            and sketch.persistent_ref
            and entity.sketch_persistent_ref != sketch.persistent_ref
        ):
            raise EntityReferenceInvalidError(
                "sketch entity belongs to a different sketch",
                operation="solidworks.entity.resolve",
                details={"entity_id": entity.id, "sketch_id": sketch.id},
            )
        resolved = resolve_persist_reference(model.Extension, entity.persistent_ref)
        sketch_object = self._active_sketch_object(
            model, sketch, self._resolve_sketch(model, sketch)
        )
        segment_refs = {
            self._persistent_ref(model, segment)
            for segment in _com_collection(sketch_object, "GetSketchSegments")
        }
        if entity.persistent_ref not in segment_refs:
            raise EntityReferenceInvalidError(
                "persistent reference does not belong to the requested sketch",
                operation="solidworks.entity.resolve",
                details={"entity_id": entity.id, "sketch_id": sketch.id},
            )
        return resolved

    def _resolve_entities(
        self,
        model: Any,
        sketch: SketchHandle,
        entities: tuple[SketchEntityHandle, ...],
    ) -> tuple[Any, ...]:
        if not entities:
            raise ComOperationError(
                "at least one sketch entity is required",
                operation="solidworks.sketch.selection",
            )
        return tuple(self._resolve_entity(model, sketch, entity) for entity in entities)

    @staticmethod
    def _select_objects(model: Any, objects: tuple[Any, ...]) -> None:
        model.ClearSelection2(True)
        for index, obj in enumerate(objects):
            if not obj.Select2(index > 0, 0):
                raise ComOperationError(
                    "resolved sketch entity could not be selected",
                    operation="solidworks.sketch.selection",
                )

    @staticmethod
    def _select_coincident_endpoints(
        model: Any,
        entities: tuple[SketchEntityHandle, ...],
        objects: tuple[Any, ...],
    ) -> None:
        first, second = entities
        first_points = _entity_endpoints(first)
        second_points = _entity_endpoints(second)
        pairs = [
            (point, other)
            for point in first_points
            for other in second_points
            if (
                abs(point[0] - other[0]) <= _SKETCH_POINT_TOLERANCE_MM
                and abs(point[1] - other[1]) <= _SKETCH_POINT_TOLERANCE_MM
            )
        ]
        if len(pairs) != 1:
            raise ComOperationError(
                "coincident relation requires exactly one unambiguous shared endpoint",
                operation="solidworks.add_relation",
            )
        first_point, second_point = pairs[0]
        try:
            import pythoncom

            for index, (obj, point) in enumerate(
                zip(objects, (first_point, second_point), strict=True)
            ):
                name = str(_com_value(obj, "GetName"))
                selected = model.Extension.SelectByID2(
                    name,
                    "SKETCHPOINT",
                    mm_to_sw_m(point[0]),
                    mm_to_sw_m(point[1]),
                    0.0,
                    index > 0,
                    0,
                    pythoncom.Nothing,
                    0,
                )
                if not selected:
                    raise ComOperationError(  # noqa: TRY301
                        "resolved sketch endpoint could not be selected",
                        operation="solidworks.sketch.selection",
                    )
        except ComOperationError:
            raise
        except Exception as exc:
            raise ComOperationError(
                "resolved sketch endpoints could not be selected",
                operation="solidworks.sketch.selection",
            ) from exc

    @staticmethod
    def _select_origin_endpoint(
        model: Any,
        entity: SketchEntityHandle,
        obj: Any,
    ) -> None:
        endpoints = [
            point
            for point in _entity_endpoints(entity)
            if (
                abs(point[0]) <= _SKETCH_POINT_TOLERANCE_MM
                and abs(point[1]) <= _SKETCH_POINT_TOLERANCE_MM
            )
        ]
        if len(endpoints) != 1:
            raise ComOperationError(
                "origin anchor requires exactly one endpoint at the sketch origin",
                operation="solidworks.sketch.selection",
            )
        endpoint = endpoints[0]
        try:
            import pythoncom

            name = str(_com_value(obj, "GetName"))
            if not model.Extension.SelectByID2(
                name,
                "SKETCHPOINT",
                mm_to_sw_m(endpoint[0]),
                mm_to_sw_m(endpoint[1]),
                0.0,
                False,
                0,
                pythoncom.Nothing,
                0,
            ):
                raise ComOperationError(  # noqa: TRY301
                    "resolved sketch endpoint could not be selected",
                    operation="solidworks.sketch.selection",
                )
            if not model.Extension.SelectByID2(
                "",
                "EXTSKETCHPOINT",
                0.0,
                0.0,
                0.0,
                True,
                0,
                pythoncom.Nothing,
                0,
            ):
                raise ComOperationError(  # noqa: TRY301
                    "sketch origin could not be selected",
                    operation="solidworks.sketch.selection",
                )
        except ComOperationError:
            raise
        except Exception as exc:
            raise ComOperationError(
                "resolved sketch origin could not be selected",
                operation="solidworks.sketch.selection",
            ) from exc

    def _resolve_dimension(
        self,
        model: Any,
        sketch: SketchHandle,
        dimension: DimensionHandle,
    ) -> Any:
        if not dimension.name.endswith(f"@{sketch.name}"):
            raise EntityReferenceInvalidError(
                "sketch dimension belongs to a different sketch",
                operation="solidworks.dimension.resolve",
                details={"dimension_id": dimension.id, "sketch_id": sketch.id},
            )
        if dimension.persistent_ref:
            return resolve_persist_reference(model.Extension, dimension.persistent_ref)
        try:
            resolved = model.Parameter(dimension.name)
        except Exception as exc:
            raise EntityReferenceInvalidError(
                "sketch dimension could not be resolved",
                operation="solidworks.dimension.resolve",
                details={"dimension_id": dimension.id, "name": dimension.name},
            ) from exc
        if resolved is None:
            raise EntityReferenceInvalidError(
                "sketch dimension could not be resolved",
                operation="solidworks.dimension.resolve",
                details={"dimension_id": dimension.id, "name": dimension.name},
            )
        return resolved

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
        geometry.finish_sketch(model)
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
        self._document_handles.pop(document.id, None)
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
                known_handle = self._document_handles[document_id]
                raw_path = str(document.GetPathName)
                return DocumentHandle(
                    id=document_id,
                    document_type=documents.document_type(document),
                    title=str(document.GetTitle),
                    path=Path(raw_path) if raw_path else known_handle.path,
                    configuration=known_handle.configuration,
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
        self._document_handles[handle.id] = handle
        return handle

    @staticmethod
    def _same_document(left: Any, right: Any) -> bool:
        try:
            return left is right or (
                left.GetPathName == right.GetPathName and left.GetTitle == right.GetTitle
            )
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


def _add_dimension(
    model: Any,
    dimension_type: DimensionType,
    position_x_mm: float,
    position_y_mm: float,
) -> Any:
    x = mm_to_sw_m(position_x_mm)
    y = mm_to_sw_m(position_y_mm)
    if dimension_type is DimensionType.HORIZONTAL_DISTANCE:
        return model.AddHorizontalDimension2(x, y, 0.0)
    if dimension_type is DimensionType.VERTICAL_DISTANCE:
        return model.AddVerticalDimension2(x, y, 0.0)
    if dimension_type is DimensionType.RADIUS:
        return model.AddRadialDimension2(x, y, 0.0)
    if dimension_type is DimensionType.DIAMETER:
        return model.AddDiameterDimension2(x, y, 0.0)
    return model.AddDimension2(x, y, 0.0)


def _com_collection(obj: Any, name: str) -> tuple[Any, ...]:
    value = getattr(obj, name, ())
    if callable(value):
        value = value()
    return tuple(value or ())


def _com_value(obj: Any, name: str, *args: Any) -> Any:
    value = getattr(obj, name)
    return value(*args) if callable(value) else value


def _parameter_exists(model: Any, name: str) -> bool:
    try:
        return model.Parameter(name) is not None
    except Exception:
        return False


def _entity_endpoints(entity: SketchEntityHandle) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    if entity.start_x_mm is not None and entity.start_y_mm is not None:
        points.append((entity.start_x_mm, entity.start_y_mm))
    if entity.end_x_mm is not None and entity.end_y_mm is not None:
        points.append((entity.end_x_mm, entity.end_y_mm))
    return tuple(points)


def _has_exact_shared_endpoint(entities: tuple[SketchEntityHandle, ...]) -> bool:
    if len(entities) != 2:
        return False
    first = _entity_endpoints(entities[0])
    second = _entity_endpoints(entities[1])
    return any(point == other for point in first for other in second)
