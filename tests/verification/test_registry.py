from __future__ import annotations

import pytest

from cadipy.domain.errors import VerificationError
from cadipy.operations.schema import PostconditionSpec
from cadipy.verification.registry import (
    register_postcondition,
    verify_postconditions,
)


def test_required_postcondition_failure_raises_verification_error() -> None:
    name = "test.required.false"
    register_postcondition(name, lambda data, inspection: False)

    with pytest.raises(VerificationError, match=name):
        verify_postconditions(
            (PostconditionSpec(name=name),),
            {},
            None,
        )


def test_optional_postcondition_failure_does_not_raise() -> None:
    name = "test.optional.false"
    register_postcondition(name, lambda data, inspection: False)

    verify_postconditions(
        (PostconditionSpec(name=name, required=False),),
        {},
        None,
    )


def test_postcondition_registration_rejects_duplicate_names() -> None:
    name = "test.duplicate"
    register_postcondition(name, lambda data, inspection: True)

    with pytest.raises(ValueError, match="already registered"):
        register_postcondition(name, lambda data, inspection: True)
