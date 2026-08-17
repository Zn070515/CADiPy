from __future__ import annotations

import json

import pytest

from cadipy.domain.errors import VerificationError
from cadipy.domain.execution import ExecutionPhase, ExecutionReport, RollbackStatus
from cadipy.protocol.result import OperationResult


def test_execution_report_round_trips_to_serializable_values() -> None:
    report = ExecutionReport(
        phase=ExecutionPhase.COMMITTED,
        state_certainty="certain",
        rollback_status=RollbackStatus.NOT_ATTEMPTED,
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
        "rollback_status": "not_attempted",
    }


def test_execution_phase_values_are_exact_protocol_values() -> None:
    assert tuple(phase.value for phase in ExecutionPhase) == (
        "received",
        "validated",
        "target_resolved",
        "executed",
        "rebuilt",
        "verified",
        "committed",
        "failed",
    )


def test_rollback_status_values_are_exact_protocol_values() -> None:
    assert tuple(status.value for status in RollbackStatus) == (
        "not_attempted",
        "rolled_back",
        "rollback_failed",
        "state_uncertain",
    )


def test_execution_report_transitions_are_immutable_and_valid() -> None:
    received = ExecutionReport(
        phase=ExecutionPhase.RECEIVED,
        state_certainty="certain",
        rollback_status=RollbackStatus.NOT_ATTEMPTED,
    )

    validated = received.transition(ExecutionPhase.VALIDATED)
    resolved = validated.transition(ExecutionPhase.TARGET_RESOLVED)

    assert received.phase is ExecutionPhase.RECEIVED
    assert validated.phase is ExecutionPhase.VALIDATED
    assert resolved.phase is ExecutionPhase.TARGET_RESOLVED
    assert resolved.rollback_status is RollbackStatus.NOT_ATTEMPTED


@pytest.mark.parametrize(
    ("current", "next_phase"),
    [
        (ExecutionPhase.RECEIVED, ExecutionPhase.EXECUTED),
        (ExecutionPhase.COMMITTED, ExecutionPhase.FAILED),
        (ExecutionPhase.FAILED, ExecutionPhase.RECEIVED),
    ],
)
def test_execution_report_rejects_invalid_transitions(
    current: ExecutionPhase, next_phase: ExecutionPhase
) -> None:
    report = ExecutionReport(current, "certain", RollbackStatus.NOT_ATTEMPTED)

    with pytest.raises(ValueError, match="invalid execution phase transition"):
        report.transition(next_phase)


def test_operation_failure_preserves_error_and_execution_report() -> None:
    report = ExecutionReport(
        phase=ExecutionPhase.FAILED,
        state_certainty="uncertain",
        rollback_status=RollbackStatus.STATE_UNCERTAIN,
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
    assert result.to_dict()["execution"]["phase"] == "failed"


def test_success_and_failure_results_are_json_safe() -> None:
    success = OperationResult(
        ok=True,
        request_id="r-success",
        operation="application.info",
        execution=ExecutionReport(
            ExecutionPhase.COMMITTED,
            "certain",
            RollbackStatus.NOT_ATTEMPTED,
        ),
    )
    failure = OperationResult.failure(
        "r-failure",
        "application.info",
        VerificationError("failed"),
        execution=ExecutionReport(
            ExecutionPhase.FAILED,
            "uncertain",
            RollbackStatus.STATE_UNCERTAIN,
        ),
    )

    assert json.loads(json.dumps(success.to_dict()))["execution"]["phase"] == "committed"
    assert json.loads(json.dumps(failure.to_dict()))["error"]["code"] == "verification_failed"


def test_verification_error_has_stable_failure_code() -> None:
    assert VerificationError("failed").code == "verification_failed"
