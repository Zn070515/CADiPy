"""Serializable execution state for CADiPy operation results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ExecutionPhase(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    TARGET_RESOLVED = "target_resolved"
    EXECUTED = "executed"
    REBUILT = "rebuilt"
    VERIFIED = "verified"
    COMMITTED = "committed"
    VERIFICATION_FAILED = "verification_failed"
    FAILED = "failed"


class RollbackStatus(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
    STATE_UNCERTAIN = "state_uncertain"


_ALLOWED_TRANSITIONS: dict[ExecutionPhase, frozenset[ExecutionPhase]] = {
    ExecutionPhase.RECEIVED: frozenset({ExecutionPhase.VALIDATED, ExecutionPhase.FAILED}),
    ExecutionPhase.VALIDATED: frozenset({ExecutionPhase.TARGET_RESOLVED, ExecutionPhase.FAILED}),
    ExecutionPhase.TARGET_RESOLVED: frozenset({ExecutionPhase.EXECUTED, ExecutionPhase.FAILED}),
    ExecutionPhase.EXECUTED: frozenset(
        {
            ExecutionPhase.REBUILT,
            ExecutionPhase.VERIFIED,
            ExecutionPhase.VERIFICATION_FAILED,
            ExecutionPhase.FAILED,
        }
    ),
    ExecutionPhase.REBUILT: frozenset(
        {ExecutionPhase.VERIFIED, ExecutionPhase.VERIFICATION_FAILED, ExecutionPhase.FAILED}
    ),
    ExecutionPhase.VERIFIED: frozenset(
        {ExecutionPhase.COMMITTED, ExecutionPhase.VERIFICATION_FAILED, ExecutionPhase.FAILED}
    ),
    ExecutionPhase.COMMITTED: frozenset(),
    ExecutionPhase.VERIFICATION_FAILED: frozenset(),
    ExecutionPhase.FAILED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    phase: ExecutionPhase
    state_certainty: Literal["certain", "uncertain"]
    rollback_status: RollbackStatus

    def __post_init__(self) -> None:
        if not isinstance(self.phase, ExecutionPhase):
            raise TypeError("phase must be an ExecutionPhase")
        if self.state_certainty not in {"certain", "uncertain"}:
            raise ValueError("state_certainty must be certain or uncertain")
        if not isinstance(self.rollback_status, RollbackStatus):
            raise TypeError("rollback_status must be a RollbackStatus")

    def transition(
        self,
        phase: ExecutionPhase,
        *,
        state_certainty: Literal["certain", "uncertain"] | None = None,
        rollback_status: RollbackStatus | None = None,
    ) -> ExecutionReport:
        """Return a new report after a valid lifecycle phase transition."""
        if not isinstance(phase, ExecutionPhase):
            raise TypeError("phase must be an ExecutionPhase")
        if phase not in _ALLOWED_TRANSITIONS[self.phase]:
            raise ValueError(
                f"invalid execution phase transition: {self.phase.value} -> {phase.value}"
            )
        return ExecutionReport(
            phase=phase,
            state_certainty=(self.state_certainty if state_certainty is None else state_certainty),
            rollback_status=(self.rollback_status if rollback_status is None else rollback_status),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "phase": self.phase.value,
            "state_certainty": self.state_certainty,
            "rollback_status": self.rollback_status.value,
        }
