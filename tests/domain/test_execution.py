from __future__ import annotations

from cadipy.domain.errors import VerificationError
from cadipy.domain.execution import ExecutionPhase, ExecutionReport, RollbackStatus
from cadipy.protocol.result import OperationResult


def test_execution_report_round_trips_to_serializable_values() -> None:
    report = ExecutionReport(
        phase=ExecutionPhase.COMMITTED,
        state_certainty="certain",
        rollback_status=RollbackStatus.NOT_REQUIRED,
    )
    result = OperationResult(
        ok=True,
        request_id="r-1",
        operation="application.info",
        execution=report,
    )

    assert result.to_dict()["execution"] == {
        "phase": "committed",
        "state_certainty": "certain",
        "rollback_status": "not_required",
    }


def test_execution_phase_values_are_serializable_protocol_values() -> None:
    assert {phase.value for phase in ExecutionPhase} == {
        "received",
        "validated",
        "target_resolved",
        "executed",
        "rebuilt",
        "verified",
        "committed",
        "validation_failed",
        "target_failed",
        "execution_failed",
        "rebuild_failed",
        "verification_failed",
        "rollback_attempted",
        "rolled_back",
        "rollback_failed",
        "state_uncertain",
    }


def test_operation_failure_preserves_error_and_execution_report() -> None:
    report = ExecutionReport(
        phase=ExecutionPhase.VERIFICATION_FAILED,
        state_certainty="certain",
        rollback_status=RollbackStatus.ROLLED_BACK,
    )

    result = OperationResult.failure(
        "r-2",
        "part.create_rectangular_extrude",
        VerificationError("failed"),
        execution=report,
    )

    assert result.ok is False
    assert result.error == {
        "code": "verification_failed",
        "message": "failed",
        "operation": "part.create_rectangular_extrude",
        "details": {},
    }
    assert result.to_dict()["execution"]["phase"] == "verification_failed"


def test_verification_error_has_stable_failure_code() -> None:
    assert VerificationError("failed").code == "verification_failed"
