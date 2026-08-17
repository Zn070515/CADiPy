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
    VALIDATION_FAILED = "validation_failed"
    TARGET_FAILED = "target_failed"
    EXECUTION_FAILED = "execution_failed"
    REBUILD_FAILED = "rebuild_failed"
    VERIFICATION_FAILED = "verification_failed"
    ROLLBACK_ATTEMPTED = "rollback_attempted"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
    STATE_UNCERTAIN = "state_uncertain"


class RollbackStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    NOT_ATTEMPTED = "not_attempted"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    phase: ExecutionPhase
    state_certainty: Literal["certain", "uncertain"]
    rollback_status: RollbackStatus

    def to_dict(self) -> dict[str, str]:
        return {
            "phase": self.phase.value,
            "state_certainty": self.state_certainty,
            "rollback_status": self.rollback_status.value,
        }
