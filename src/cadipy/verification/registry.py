"""Stable registry and enforcement for operation postconditions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, cast

from cadipy.domain.errors import VerificationError

if TYPE_CHECKING:
    from cadipy.operations.schema import PostconditionSpec

PostconditionVerifier = Callable[[Mapping[str, Any], Any], Any]
_POSTCONDITIONS: dict[str, PostconditionVerifier] = {}


def register_postcondition(name: str, verifier: PostconditionVerifier) -> None:
    if name in _POSTCONDITIONS:
        raise ValueError(f"postcondition {name!r} is already registered")
    _POSTCONDITIONS[name] = verifier


def verify_postconditions(
    specs: tuple[PostconditionSpec, ...],
    operation_data: Mapping[str, Any],
    inspection: Any,
) -> None:
    for spec in specs:
        verifier = (
            cast("PostconditionVerifier", spec.verifier)
            if callable(spec.verifier)
            else _POSTCONDITIONS.get(spec.verifier or spec.name)
        )
        if verifier is None:
            raise VerificationError(
                f"postcondition {spec.name!r} has no registered verifier",
                details={"postcondition": spec.name},
            )
        outcome = verifier(operation_data, inspection)
        passed = outcome.passed if hasattr(outcome, "passed") else bool(outcome)
        if not passed and spec.required:
            raise VerificationError(
                f"postcondition {spec.name!r} failed",
                details={"postcondition": spec.name},
            )


def _data_value(name: str) -> PostconditionVerifier:
    return lambda data, _inspection: bool(data.get(name) or data.get("id"))


register_postcondition(
    "document_is_part",
    lambda data, inspection: _inspection_type(data, inspection) == "part",
)
register_postcondition(
    "rebuild_succeeded",
    lambda data, inspection: (
        data.get("rebuild") == "ok"
        or data.get("success") is True
        or bool(getattr(inspection, "rebuild_success", False))
    ),
)
register_postcondition(
    "application.visible == visible",
    lambda data, _inspection: isinstance(data.get("visible"), bool),
)
register_postcondition(
    "feature_exists",
    lambda data, inspection: (
        bool(getattr(inspection, "feature_names", ())) or bool(data.get("feature"))
    ),
)
register_postcondition("sketch_exists", _data_value("sketch"))
register_postcondition("entity_exists", _data_value("entity"))
register_postcondition(
    "four_entities_exist",
    lambda data, _inspection: len(data.get("entities", ())) == 4,
)
register_postcondition("relation_exists", _data_value("relation"))
register_postcondition("dimension_exists", _data_value("dimension"))
register_postcondition("dimension_value_matches", _data_value("dimension"))
register_postcondition(
    "rectangular_extrusion",
    lambda data, _inspection: data.get("verification_report", {}).get("passed", False),
)


def _inspection_type(data: Mapping[str, Any], inspection: Any) -> str | None:
    value = getattr(inspection, "document_type", None)
    if value is None and isinstance(inspection, Mapping):
        value = inspection.get("document_type")
    if value is not None:
        resolved = getattr(value, "value", value)
        return resolved if isinstance(resolved, str) else None
    return data.get("document_type") or (
        data.get("inspection", {}).get("document_type")
        if isinstance(data.get("inspection"), Mapping)
        else None
    )
