from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from cadipy.domain.errors import InvalidArgumentError
from cadipy.operations.schema import (
    ParamSpec,
    ParamType,
    PostconditionSpec,
    validate_parameter,
    validate_parameters,
)


def test_parameter_and_postcondition_specs_are_immutable() -> None:
    parameter = ParamSpec(type=ParamType.STRING, required=True)
    postcondition = PostconditionSpec(name="feature_exists")

    with pytest.raises(FrozenInstanceError):
        parameter.required = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        postcondition.required = False  # type: ignore[misc]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_finite_number_rejects_non_finite_values(value: float) -> None:
    spec = ParamSpec(type=ParamType.NUMBER, required=True, finite=True)

    with pytest.raises(InvalidArgumentError):
        validate_parameter("depth_mm", spec, value, operation="part.test")


def test_boolean_is_not_accepted_as_number() -> None:
    spec = ParamSpec(type=ParamType.NUMBER, required=True)

    with pytest.raises(InvalidArgumentError):
        validate_parameter("depth_mm", spec, True, operation="part.test")


def test_numeric_bounds_and_choices_are_enforced() -> None:
    minimum = ParamSpec(type=ParamType.NUMBER, exclusive_minimum=0.0)
    choices = ParamSpec(type=ParamType.STRING, choices=frozenset({"front", "top"}))

    with pytest.raises(InvalidArgumentError):
        validate_parameter("radius_mm", minimum, 0.0, operation="part.test")
    with pytest.raises(InvalidArgumentError):
        validate_parameter("plane", choices, "right", operation="sketch.create")


@pytest.mark.parametrize(
    ("spec", "value"),
    [
        (ParamSpec(type=ParamType.BOOLEAN), 1),
        (ParamSpec(type=ParamType.INTEGER), 1.0),
        (ParamSpec(type=ParamType.STRING), 1),
        (ParamSpec(type=ParamType.PATH), 1),
        (ParamSpec(type=ParamType.OBJECT), []),
        (ParamSpec(type=ParamType.ARRAY), {}),
    ],
)
def test_primitive_types_are_checked_without_coercion(spec: ParamSpec, value: object) -> None:
    with pytest.raises(InvalidArgumentError):
        validate_parameter("value", spec, value, operation="part.test")


def test_validate_parameters_rejects_unknown_and_missing_values_and_applies_defaults() -> None:
    spec = {
        "required": ParamSpec(type=ParamType.STRING, required=True),
        "optional": ParamSpec(type=ParamType.INTEGER, default=3),
    }

    with pytest.raises(InvalidArgumentError):
        validate_parameters(spec, {}, operation="part.test")
    with pytest.raises(InvalidArgumentError):
        validate_parameters(spec, {"required": "ok", "extra": True}, operation="part.test")
    assert validate_parameters(spec, {"required": "ok"}, operation="part.test") == {
        "required": "ok",
        "optional": 3,
    }


def test_schema_values_are_json_compatible() -> None:
    parameter = ParamSpec(
        type=ParamType.NUMBER,
        required=True,
        default=None,
        unit="mm",
        finite=True,
        minimum=0.0,
        exclusive_maximum=100.0,
        choices=None,
    )
    postcondition = PostconditionSpec(name="feature_exists", required=True)

    assert json.dumps(parameter.to_dict())
    assert json.dumps(postcondition.to_dict())
