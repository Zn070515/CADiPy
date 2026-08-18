from __future__ import annotations

import pytest

from cadipy.api import connect
from cadipy.domain.errors import VerificationError
from cadipy.protocol.result import OperationResult
from cadipy.verification.postconditions import VerificationCheck, VerificationReport


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_required_postcondition_failure_is_reported(
    solidworks_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cadipy.operations.dispatch as dispatch_module

    def forced_failure(*args: object, **kwargs: object) -> VerificationReport:
        del args, kwargs
        return VerificationReport(
            passed=False,
            status="failed",
            checks=(
                VerificationCheck(
                    name="test_forced_postcondition",
                    passed=False,
                    expected=True,
                    observed=False,
                ),
            ),
        )

    monkeypatch.setattr(dispatch_module, "verify_rectangular_extrusion", forced_failure)
    request = {
        "protocol": 1,
        "id": "strict-required-verification-failure",
        "operation": "part.create_rectangular_extrude",
        "params": {"width_mm": 100.0, "height_mm": 60.0, "depth_mm": 3.0},
    }
    try:
        solidworks_session.dispatch_request(request)
    except VerificationError as exc:
        result = OperationResult.failure(request["id"], request["operation"], exc)
    else:
        pytest.fail("forced verification failure unexpectedly returned successfully")

    assert result.ok is False
    assert result.error is not None
    assert result.error["code"] == "verification_failed"
    assert result.execution is not None
    assert result.execution.phase.value == "failed"
    assert result.execution.rollback_status.value == "rolled_back"


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_attached_user_owned_application_survives_session_disconnect(
    user_owned_application,
    user_owned_executor_factory,
) -> None:
    with connect(
        mode="attach",
        executor_factory=user_owned_executor_factory,
    ) as session:
        result = session.execute("application.info")

        assert result.ok is True
        assert result.data is not None
        assert result.data["connection_mode"] == "attach"
        assert result.data["owned"] is False

    assert user_owned_application() is True
