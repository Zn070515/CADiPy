"""Validate and dispatch every public operation through one path."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from cadipy.audit.events import AuditEvent
from cadipy.backends.executor import DocumentHandle, SolidWorksExecutor
from cadipy.domain.errors import InvalidArgumentError, ProtocolError, TargetNotFoundError
from cadipy.domain.documents import DocumentType
from cadipy.domain.targets import TargetBinding
from cadipy.protocol.result import OperationResult
from cadipy.verification.postconditions import verify_rectangular_extrusion

from .registry import OPERATION_REGISTRY, OpSpec

if TYPE_CHECKING:
    from cadipy.audit.recorder import AuditRecorder

TargetResolver = Callable[[TargetBinding], DocumentHandle]


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
        if not isinstance(operation, str) or operation not in OPERATION_REGISTRY:
            raise ProtocolError("unknown CAD operation", details={"operation": operation})
        spec = OPERATION_REGISTRY[operation]
        params = request.get("params", {})
        if not isinstance(params, Mapping):
            raise InvalidArgumentError("operation params must be an object")
        normalized = self._validate_params(spec, params)
        target = self._resolve_target(spec, request.get("target"))
        data = self._invoke(operation, normalized, target)
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
        )

    def _validate_params(self, spec: OpSpec, params: Mapping[str, Any]) -> dict[str, Any]:
        unknown = set(params) - set(spec.parameters)
        if unknown:
            raise InvalidArgumentError(
                "operation contains unknown parameters",
                operation=spec.name,
                details={"unknown": sorted(unknown)},
            )
        normalized = dict(params)
        for name, declaration in spec.parameters.items():
            if declaration.get("required") and name not in normalized:
                raise InvalidArgumentError(
                    f"missing required parameter: {name}",
                    operation=spec.name,
                    details={"parameter": name},
                )
            if name not in normalized:
                if "default" in declaration:
                    normalized[name] = declaration["default"]
                continue
            value = normalized[name]
            type_name = declaration.get("type")
            if type_name == "number" and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                raise InvalidArgumentError(
                    f"parameter {name} must be a number",
                    operation=spec.name,
                    details={"parameter": name},
                )
            if type_name in {"string", "path"} and not isinstance(value, str):
                raise InvalidArgumentError(
                    f"parameter {name} must be a string",
                    operation=spec.name,
                    details={"parameter": name},
                )
        return normalized

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
        return self.target_resolver(binding)

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
            return _dict(self.executor.launch())
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
            document_type = DocumentType(params["document_type"])
            return _handle_dict(
                self.executor.open_document(Path(params["path"]), document_type)
            )
        if operation == "document.close":
            assert target is not None
            self.executor.close(target)
            return {"closed_document_id": target.id}
        if operation == "document.inspect":
            assert target is not None
            return _dict(self.executor.inspect_document(target))
        if operation == "part.rebuild":
            assert target is not None
            return _dict(self.executor.rebuild(target))
        if operation == "part.create_rectangular_extrude":
            document = self.executor.create_part()
            sketch = self.executor.create_sketch(document, params["plane"])
            rectangle = self.executor.add_rectangle(
                sketch,
                params["width_mm"],
                params["height_mm"],
            )
            feature = self.executor.extrude(document, sketch, params["depth_mm"])
            rebuild = self.executor.rebuild(document)
            inspection = self.executor.inspect_document(document)
            verification = verify_rectangular_extrusion(
                inspection,
                params["width_mm"],
                params["height_mm"],
                params["depth_mm"],
            )
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
                path = Path(params["save_path"])
                save = self.executor.save(document, path)
                self.executor.close(document)
                reopened = self.executor.reopen(path)
                data["save"] = _dict(save)
                data["reopened_document"] = _handle_dict(reopened)
                reopened_rebuild = self.executor.rebuild(reopened)
                reopened_inspection = self.executor.inspect_document(reopened)
                reopened_verification = verify_rectangular_extrusion(
                    reopened_inspection,
                    params["width_mm"],
                    params["height_mm"],
                    params["depth_mm"],
                )
                data["reopened_rebuild"] = "ok" if reopened_rebuild.success else "failed"
                data["reopened_inspection"] = _dict(reopened_inspection)
                data["reopened_verification"] = reopened_verification.to_dict()
            return data
        raise ProtocolError("operation has no dispatcher handler", details={"operation": operation})


def _handle_dict(value: Any) -> dict[str, Any]:
    return _dict(value)


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
