"""Immutable, serializable schemas for public CAD operations."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from cadipy.domain.errors import InvalidArgumentError


class ParamType(str, Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    PATH = "path"
    OBJECT = "object"
    ARRAY = "array"


_MISSING = object()


@dataclass(frozen=True, slots=True)
class ParamSpec:
    type: ParamType
    required: bool = False
    default: Any = field(default=_MISSING, repr=False)
    unit: str | None = None
    finite: bool = False
    minimum: float | None = None
    exclusive_minimum: float | None = None
    maximum: float | None = None
    exclusive_maximum: float | None = None
    choices: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.type, ParamType):
            object.__setattr__(self, "type", ParamType(self.type))
        if self.choices is not None and not isinstance(self.choices, frozenset):
            object.__setattr__(self, "choices", frozenset(self.choices))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.type.value,
            "required": self.required,
        }
        if self.default is not _MISSING:
            result["default"] = self.default
        if self.unit is not None:
            result["unit"] = self.unit
        if self.finite:
            result["finite"] = True
        for name in ("minimum", "exclusive_minimum", "maximum", "exclusive_maximum"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if self.choices is not None:
            result["choices"] = sorted(self.choices)
        return result

    def __getitem__(self, key: str) -> Any:
        """Read legacy dictionary keys while callers migrate to typed fields."""
        return self.to_dict()[key]


Verifier = Callable[[Any], Any] | str


@dataclass(frozen=True, slots=True)
class PostconditionSpec:
    name: str
    required: bool = True
    verifier: Verifier | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name, "required": self.required}
        if self.verifier is not None:
            result["verifier"] = (
                self.verifier if isinstance(self.verifier, str) else self.verifier.__name__
            )
        return result


def validate_parameter(
    name: str,
    spec: ParamSpec,
    value: Any,
    *,
    operation: str,
) -> Any:
    valid = {
        ParamType.BOOLEAN: isinstance(value, bool),
        ParamType.INTEGER: isinstance(value, int) and not isinstance(value, bool),
        ParamType.NUMBER: isinstance(value, (int, float)) and not isinstance(value, bool),
        ParamType.STRING: isinstance(value, str),
        ParamType.PATH: isinstance(value, str),
        ParamType.OBJECT: isinstance(value, Mapping),
        ParamType.ARRAY: isinstance(value, (list, tuple)),
    }[spec.type]
    if not valid:
        raise _invalid(name, f"parameter {name} must be a {spec.type.value}", operation)

    if spec.type in {ParamType.INTEGER, ParamType.NUMBER}:
        numeric = float(value)
        if spec.finite and not math.isfinite(numeric):
            raise _invalid(name, f"parameter {name} must be finite", operation)
        if spec.minimum is not None and numeric < spec.minimum:
            raise _invalid(name, f"parameter {name} is below the minimum", operation)
        if spec.exclusive_minimum is not None and numeric <= spec.exclusive_minimum:
            raise _invalid(
                name, f"parameter {name} must be greater than the exclusive minimum", operation
            )
        if spec.maximum is not None and numeric > spec.maximum:
            raise _invalid(name, f"parameter {name} is above the maximum", operation)
        if spec.exclusive_maximum is not None and numeric >= spec.exclusive_maximum:
            raise _invalid(
                name, f"parameter {name} must be less than the exclusive maximum", operation
            )
    if spec.choices is not None and value not in spec.choices:
        raise _invalid(name, f"parameter {name} is not an allowed choice", operation)
    return value


def validate_parameters(
    specs: Mapping[str, ParamSpec], params: Mapping[str, Any], *, operation: str
) -> dict[str, Any]:
    unknown = set(params) - set(specs)
    if unknown:
        raise InvalidArgumentError(
            "operation contains unknown parameters",
            operation=operation,
            details={"unknown": sorted(unknown)},
        )
    normalized = dict(params)
    for name, spec in specs.items():
        if name not in normalized:
            if spec.required:
                raise InvalidArgumentError(
                    f"missing required parameter: {name}",
                    operation=operation,
                    details={"parameter": name},
                )
            if spec.default is not _MISSING:
                normalized[name] = spec.default
        if name in normalized:
            validate_parameter(name, spec, normalized[name], operation=operation)
    return normalized


def _invalid(name: str, message: str, operation: str) -> InvalidArgumentError:
    return InvalidArgumentError(message, operation=operation, details={"parameter": name})
