from cadipy.domain.errors import TargetNotFoundError


def test_domain_error_exposes_stable_code_and_operation_context() -> None:
    error = TargetNotFoundError(
        "target is required",
        operation="part.create_extrude",
        details={"document_type": "part"},
    )

    assert error.code == "target_not_found"
    assert error.operation == "part.create_extrude"
    assert error.details == {"document_type": "part"}
    assert str(error) == "target is required"
