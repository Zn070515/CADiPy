"""Validate and dispatch every public operation through one path."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from cadipy.audit.events import AuditEvent
from cadipy.backends.executor import DocumentHandle, SketchHandle, SolidWorksExecutor
from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import (
    CapabilityUnavailableError,
    DocumentTypeError,
    InvalidArgumentError,
    ProtocolError,
    TargetNotFoundError,
    TransactionError,
    VerificationError,
)
from cadipy.domain.execution import ExecutionPhase, ExecutionReport, RollbackStatus
from cadipy.domain.identities import DocumentIdentity
from cadipy.domain.sketches import (
    DimensionHandle,
    DimensionType,
    RelationType,
    SketchEntityHandle,
    SketchEntityType,
)
from cadipy.domain.targets import TargetBinding
from cadipy.protocol.result import OperationResult
from cadipy.runtime.mutation import (
    MutationAction,
    MutationCapability,
    MutationScope,
    MutationSnapshot,
)
from cadipy.verification.postconditions import verify_rectangular_extrusion
from cadipy.verification.registry import verify_postconditions

from .registry import OPERATION_REGISTRY, OpSpec
from .schema import validate_parameters

if TYPE_CHECKING:
    from cadipy.audit.recorder import AuditRecorder

TargetResolver = Callable[[TargetBinding], DocumentHandle]


def _mutation_capability(executor: SolidWorksExecutor) -> MutationCapability | None:
    required = (
        "mutation_state_uncertain",
        "mark_mutation_uncertain",
        "reconcile_mutation",
        "begin_mutation",
        "commit_mutation",
        "rollback_mutation",
        "verify_rollback",
    )
    return executor if all(hasattr(executor, name) for name in required) else None


class OperationDispatcher:
    def __init__(
        self,
        executor: SolidWorksExecutor,
        *,
        target_resolver: TargetResolver | None = None,
        audit_recorder: AuditRecorder | None = None,
    ) -> None:
        self.executor = executor
        self.target_resolver = target_resolver
        self.audit_recorder = audit_recorder

    def dispatch(self, request: Mapping[str, Any]) -> OperationResult:
        request_id = str(request.get("id", "request"))
        operation = request.get("operation")
        report = ExecutionReport(ExecutionPhase.RECEIVED, "certain", RollbackStatus.NOT_ATTEMPTED)
        try:
            if not isinstance(operation, str) or operation not in OPERATION_REGISTRY:
                raise ProtocolError(  # noqa: TRY301
                    "unknown CAD operation", details={"operation": operation}
                )
            spec = OPERATION_REGISTRY[operation]
            params = request.get("params", {})
            if not isinstance(params, Mapping):
                raise InvalidArgumentError(  # noqa: TRY301
                    "operation params must be an object"
                )
            normalized = self._validate_params(spec, params)
            report = report.transition(ExecutionPhase.VALIDATED)
            if spec.mutating:
                self._ensure_mutation_state(operation, report)
            target = self._resolve_target(spec, request.get("target"))
            report = report.transition(ExecutionPhase.TARGET_RESOLVED)
            data = self._invoke(operation, normalized, target)
            report = report.transition(ExecutionPhase.EXECUTED)
            inspection = _inspection_from_data(data)
            postcondition_data = dict(data)
            postcondition_data["_params"] = normalized
            verify_postconditions(spec.postconditions, postcondition_data, inspection)
            report = report.transition(ExecutionPhase.VERIFIED)
            report = report.transition(ExecutionPhase.COMMITTED)
            if self.audit_recorder is not None:
                self.audit_recorder.record(
                    AuditEvent(
                        request_id=request_id,
                        operation=operation,
                        executor_kind=self.executor.executor_kind,
                        target=dict(request["target"])
                        if isinstance(request.get("target"), Mapping)
                        else {},
                        parameters=normalized,
                        rebuild=data.get("rebuild"),
                        verification=data.get("verification"),
                    )
                )
            return OperationResult(
                ok=True,
                request_id=request_id,
                operation=operation,
                data=_serialize(data),
                execution=report,
            )
        except Exception as exc:
            scoped_report = getattr(exc, "execution", None)
            failed = scoped_report if isinstance(scoped_report, ExecutionReport) else report
            if scoped_report is None and report.phase not in {
                ExecutionPhase.FAILED,
                ExecutionPhase.VERIFICATION_FAILED,
                ExecutionPhase.COMMITTED,
            }:
                failure_phase = (
                    ExecutionPhase.VERIFICATION_FAILED
                    if isinstance(exc, VerificationError)
                    else ExecutionPhase.FAILED
                )
                failed = report.transition(
                    failure_phase,
                    state_certainty="uncertain",
                    rollback_status=(
                        RollbackStatus.STATE_UNCERTAIN
                        if isinstance(exc, CapabilityUnavailableError)
                        else None
                    ),
                )
            setattr(exc, "execution", failed)  # noqa: B010
            raise

    def reconcile_mutation(self) -> None:
        """Explicitly clear a previously persisted uncertain mutation state."""
        reconcile = getattr(self.executor, "reconcile_mutation", None)
        if not callable(reconcile):
            raise CapabilityUnavailableError(
                "executor does not provide mutation-state reconciliation"
            )
        reconcile()

    def _ensure_mutation_state(self, operation: str, report: ExecutionReport) -> None:
        state_check = getattr(self.executor, "mutation_state_uncertain", None)
        if not callable(state_check):
            return
        try:
            state_uncertain = bool(state_check())
        except BaseException as exc:
            failed = report.transition(
                ExecutionPhase.FAILED,
                state_certainty="uncertain",
                rollback_status=RollbackStatus.STATE_UNCERTAIN,
            )
            setattr(exc, "execution", failed)  # noqa: B010
            error = TransactionError(
                "mutation state could not be determined",
                operation=operation,
            )
            error.execution = failed
            raise error from exc
        if state_uncertain:
            error = TransactionError(
                "mutation is blocked by an uncertain session mutation state",
                operation=operation,
            )
            error.execution = report.transition(
                ExecutionPhase.FAILED,
                state_certainty="uncertain",
                rollback_status=RollbackStatus.STATE_UNCERTAIN,
            )
            raise error

    def _validate_params(self, spec: OpSpec, params: Mapping[str, Any]) -> dict[str, Any]:
        return validate_parameters(spec.parameters, params, operation=spec.name)

    def _resolve_target(self, spec: OpSpec, target: Any) -> DocumentHandle | None:
        if target is None:
            if spec.target_required:
                raise TargetNotFoundError(
                    "this operation requires an explicit target",
                    operation=spec.name,
                )
            return None
        if not isinstance(target, Mapping):
            raise InvalidArgumentError("target must be an object", operation=spec.name)
        if self.target_resolver is None:
            raise TargetNotFoundError("no target resolver is configured", operation=spec.name)
        binding = TargetBinding(
            document_id=target.get("document_id"),
            path=Path(target["path"]) if target.get("path") else None,
            title=target.get("title"),
            document_type=self._document_type(target.get("document_type"), spec.name),
            configuration=target.get("configuration"),
        )
        resolved = self.target_resolver(binding)
        if (
            spec.target_document_types
            and resolved.document_type.value not in spec.target_document_types
        ):
            raise DocumentTypeError(
                "target document type is not supported by this operation",
                operation=spec.name,
                details={
                    "expected": list(spec.target_document_types),
                    "actual": resolved.document_type.value,
                },
            )
        return resolved

    @staticmethod
    def _document_type(value: Any, operation: str) -> DocumentType | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise InvalidArgumentError(
                "target document_type must be a string",
                operation=operation,
            )
        try:
            return DocumentType(value)
        except ValueError as exc:
            raise InvalidArgumentError(
                "target document_type is not supported",
                operation=operation,
                details={"document_type": value},
            ) from exc

    def _invoke(
        self,
        operation: str,
        params: dict[str, Any],
        target: DocumentHandle | None,
    ) -> dict[str, Any]:
        if operation == "application.attach":
            return _dict(self.executor.attach())
        if operation == "application.launch":
            return _dict(self.executor.launch(visible=params["visible"]))
        if operation == "application.set_visibility":
            return _dict(self.executor.set_visibility(params["visible"]))
        if operation == "application.info":
            return _dict(self.executor.application_info())
        if operation == "diagnostics.connect":
            return _dict(self.executor.connect())
        if operation == "document.create_part":
            return _handle_dict(self.executor.create_part())
        if operation == "document.list":
            return {"documents": [_handle_dict(item) for item in self.executor.list_documents()]}
        if operation == "document.active":
            active = self.executor.active_document()
            return {"document": _handle_dict(active) if active is not None else None}
        if operation == "document.open":
            try:
                document_type = DocumentType(params["document_type"])
            except ValueError as exc:
                raise InvalidArgumentError(
                    "document.open document_type is not supported",
                    operation=operation,
                    details={"document_type": params["document_type"]},
                ) from exc
            return _handle_dict(self.executor.open_document(Path(params["path"]), document_type))
        if operation == "document.close":
            assert target is not None
            self.executor.close(target)
            return {"closed_document_id": target.id}
        if operation == "document.save":
            assert target is not None
            saved = self.executor.save(target, Path(params["path"]))
            if not saved.success:
                raise TransactionError(
                    "SOLIDWORKS did not save the requested document",
                    operation=operation,
                )
            return _dict(saved)
        if operation == "document.inspect":
            assert target is not None
            return _dict(self.executor.inspect_document(target))
        if operation == "part.rebuild":
            assert target is not None
            return _dict(self.executor.rebuild(target))
        if operation == "sketch.create":
            assert target is not None
            return _dict(self.executor.create_sketch(target, params["plane"]))
        if operation == "sketch.list":
            assert target is not None
            return {"sketches": [_dict(item) for item in self.executor.list_sketches(target)]}
        if operation == "sketch.inspect":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            return _dict(self.executor.inspect_sketch(target, sketch))
        if operation == "sketch.add_line":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            return _dict(
                self.executor.add_line(
                    target,
                    sketch,
                    params["start_x_mm"],
                    params["start_y_mm"],
                    params["end_x_mm"],
                    params["end_y_mm"],
                )
            )
        if operation == "sketch.add_rectangle":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            return {
                "entities": [
                    _dict(item)
                    for item in self.executor.add_sketch_rectangle(
                        target,
                        sketch,
                        params["width_mm"],
                        params["height_mm"],
                        params["origin_x_mm"],
                        params["origin_y_mm"],
                    )
                ]
            }
        if operation == "sketch.add_circle":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            return _dict(
                self.executor.add_circle(
                    target,
                    sketch,
                    params["center_x_mm"],
                    params["center_y_mm"],
                    params["radius_mm"],
                )
            )
        if operation == "sketch.add_arc":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            return _dict(
                self.executor.add_arc(
                    target,
                    sketch,
                    params["center_x_mm"],
                    params["center_y_mm"],
                    params["start_x_mm"],
                    params["start_y_mm"],
                    params["end_x_mm"],
                    params["end_y_mm"],
                    params["direction"],
                )
            )
        if operation == "sketch.add_relation":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            entities = _entities_from_value(params["entities"], operation)
            try:
                relation_type = RelationType(params["relation_type"])
            except ValueError as exc:
                raise InvalidArgumentError(
                    "unsupported sketch relation type",
                    operation=operation,
                    details={"relation_type": params["relation_type"]},
                ) from exc
            return _dict(
                self.executor.add_relation(
                    target,
                    sketch,
                    relation_type,
                    entities,
                    anchor_origin=params["anchor_origin"],
                )
            )
        if operation == "sketch.add_dimension":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            entities = _entities_from_value(params["entities"], operation)
            try:
                dimension_type = DimensionType(params["dimension_type"])
            except ValueError as exc:
                raise InvalidArgumentError(
                    "unsupported sketch dimension type",
                    operation=operation,
                    details={"dimension_type": params["dimension_type"]},
                ) from exc
            return _dict(
                self.executor.add_dimension(
                    target,
                    sketch,
                    dimension_type,
                    entities,
                    params["value_mm"],
                    params["position_x_mm"],
                    params["position_y_mm"],
                )
            )
        if operation == "sketch.set_dimension":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            dimension = _dimension_from_value(params["dimension"], operation)
            return _dict(self.executor.set_dimension(target, sketch, dimension, params["value_mm"]))
        if operation == "sketch.inspect_entity":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            entity = _entity_from_value(params["entity"], operation)
            return _dict(self.executor.inspect_entity(target, sketch, entity))
        if operation == "sketch.inspect_dimension":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            dimension = _dimension_from_value(params["dimension"], operation)
            return _dict(self.executor.inspect_dimension(target, sketch, dimension))
        if operation == "part.create_extrude":
            assert target is not None
            sketch = _sketch_from_value(params["sketch"], operation)
            return {"feature": _dict(self.executor.extrude(target, sketch, params["depth_mm"]))}
        if operation == "part.create_rectangular_extrude":
            snapshot = MutationSnapshot(
                target_identity=DocumentIdentity(
                    document_id="pending-created-part",
                    path=None,
                    title="CADiPy-created Part",
                    document_type=DocumentType.PART,
                ),
                created_resource=True,
            )
            capability = _mutation_capability(self.executor)
            if capability is None:
                mark_uncertain = getattr(self.executor, "mark_mutation_uncertain", None)
                if callable(mark_uncertain):
                    mark_uncertain()
                raise CapabilityUnavailableError(
                    "rectangular extrusion requires semantic rollback capability",
                    operation=operation,
                )
            save: Any = None
            reopened: DocumentHandle | None = None
            reopened_rebuild: Any = None
            reopened_inspection: Any = None
            reopened_verification: Any = None
            with MutationScope(capability, snapshot) as scope:
                document = scope.step("create part", self.executor.create_part)
                scope.mark_created_resource(document.id)
                sketch = scope.step(
                    "create sketch",
                    lambda: self.executor.create_sketch(document, params["plane"]),
                )
                rectangle = scope.step(
                    "create rectangle",
                    lambda: self.executor.add_rectangle(
                        sketch,
                        params["width_mm"],
                        params["height_mm"],
                    ),
                )
                feature = scope.step(
                    "create extrusion",
                    lambda: self.executor.extrude(document, sketch, params["depth_mm"]),
                )
                rebuild = scope.rebuild(lambda: self.executor.rebuild(document))
                inspection = self.executor.inspect_document(document)
                verification = verify_rectangular_extrusion(
                    inspection,
                    params["width_mm"],
                    params["height_mm"],
                    params["depth_mm"],
                )
                postconditions: list[MutationAction] = [lambda: verification.passed]
                if params.get("save_path"):
                    path = Path(params["save_path"])
                    save = scope.step("save", lambda: self.executor.save(document, path))
                    if not getattr(save, "success", False):
                        raise TransactionError("CADiPy save did not succeed")
                    scope.step("close", lambda: self.executor.close(document))
                    reopened = scope.step("reopen", lambda: self.executor.reopen(path))
                    scope.mark_created_resource(reopened.id)
                    reopened_rebuild = scope.rebuild(lambda: self.executor.rebuild(reopened))
                    reopened_inspection = scope.step(
                        "inspect reopened document",
                        lambda: self.executor.inspect_document(reopened),
                    )
                    reopened_verification = verify_rectangular_extrusion(
                        reopened_inspection,
                        params["width_mm"],
                        params["height_mm"],
                        params["depth_mm"],
                    )
                    postconditions.append(lambda: reopened_verification.passed)
                scope.verify(postconditions)
            data: dict[str, Any] = {
                "document": _handle_dict(document),
                "sketch": _handle_dict(sketch),
                "rectangle": _handle_dict(rectangle),
                "feature": _handle_dict(feature),
                "rebuild": "ok" if rebuild.success else "failed",
                "verification": verification.status,
                "verification_report": verification.to_dict(),
                "inspection": _dict(inspection),
            }
            if params.get("save_path"):
                assert save is not None
                assert reopened is not None
                assert reopened_rebuild is not None
                assert reopened_inspection is not None
                assert reopened_verification is not None
                data["save"] = _dict(save)
                data["reopened_document"] = _handle_dict(reopened)
                data["reopened_rebuild"] = "ok" if reopened_rebuild.success else "failed"
                data["reopened_inspection"] = _dict(reopened_inspection)
                data["reopened_verification"] = reopened_verification.to_dict()
            return data
        raise ProtocolError("operation has no dispatcher handler", details={"operation": operation})


def _handle_dict(value: Any) -> dict[str, Any]:
    return _dict(value)


def _inspection_from_data(data: Mapping[str, Any]) -> Any:
    return data.get("inspection")


def _dict(value: Any) -> dict[str, Any]:
    serialized = _serialize(value)
    if not isinstance(serialized, dict):
        raise TypeError(f"expected a mapping result, got {type(serialized).__name__}")
    return serialized


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return _serialize(asdict(cast("Any", value)))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialize(item) for item in value]
    return value


def _sketch_from_value(value: Any, operation: str) -> SketchHandle:
    if isinstance(value, SketchHandle):
        return value
    if not isinstance(value, Mapping):
        raise InvalidArgumentError("sketch must be a serialized handle", operation=operation)
    try:
        return SketchHandle(
            id=str(value["id"]),
            document_id=str(value["document_id"]),
            name=str(value["name"]),
            plane=str(value["plane"]),
            persistent_ref=(str(value["persistent_ref"]) if value.get("persistent_ref") else None),
        )
    except (KeyError, TypeError) as exc:
        raise InvalidArgumentError("sketch handle is incomplete", operation=operation) from exc


def _entity_from_value(value: Any, operation: str) -> SketchEntityHandle:
    if isinstance(value, SketchEntityHandle):
        return value
    if not isinstance(value, Mapping):
        raise InvalidArgumentError("entity must be a serialized handle", operation=operation)
    try:
        return SketchEntityHandle(
            id=str(value["id"]),
            document_id=str(value["document_id"]),
            sketch_id=str(value["sketch_id"]),
            entity_type=SketchEntityType(value["entity_type"]),
            persistent_ref=str(value["persistent_ref"]),
            sketch_persistent_ref=(
                str(value["sketch_persistent_ref"]) if value.get("sketch_persistent_ref") else None
            ),
            start_x_mm=value.get("start_x_mm"),
            start_y_mm=value.get("start_y_mm"),
            end_x_mm=value.get("end_x_mm"),
            end_y_mm=value.get("end_y_mm"),
            center_x_mm=value.get("center_x_mm"),
            center_y_mm=value.get("center_y_mm"),
            radius_mm=value.get("radius_mm"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidArgumentError("entity handle is incomplete", operation=operation) from exc


def _entities_from_value(value: Any, operation: str) -> tuple[SketchEntityHandle, ...]:
    if not isinstance(value, (list, tuple)):
        raise InvalidArgumentError("entities must be an array", operation=operation)
    return tuple(_entity_from_value(item, operation) for item in value)


def _dimension_from_value(value: Any, operation: str) -> DimensionHandle:
    if isinstance(value, DimensionHandle):
        return value
    if not isinstance(value, Mapping):
        raise InvalidArgumentError("dimension must be a serialized handle", operation=operation)
    try:
        return DimensionHandle(
            id=str(value["id"]),
            sketch_id=str(value["sketch_id"]),
            dimension_type=DimensionType(value["dimension_type"]),
            name=str(value["name"]),
            value_mm=float(value["value_mm"]),
            persistent_ref=(str(value["persistent_ref"]) if value.get("persistent_ref") else None),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidArgumentError("dimension handle is incomplete", operation=operation) from exc
