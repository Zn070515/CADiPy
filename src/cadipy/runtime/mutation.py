"""Bounded semantic mutation scopes for CAD operations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from cadipy.domain.errors import CadipyError, RebuildError, TransactionError, VerificationError
from cadipy.domain.execution import ExecutionPhase, ExecutionReport, RollbackStatus
from cadipy.domain.identities import DocumentIdentity


@dataclass(frozen=True, slots=True)
class MutationSnapshot:
    target_identity: DocumentIdentity
    dirty: bool | None = None
    save_observation: str | None = None
    model_fingerprint: str | None = None
    created_resource: bool = False
    created_resource_id: str | None = None


class MutationCapability(Protocol):
    def begin_mutation(self, snapshot: MutationSnapshot) -> None: ...

    def commit_mutation(self, snapshot: MutationSnapshot) -> None: ...

    def rollback_mutation(self, snapshot: MutationSnapshot) -> None: ...

    def verify_rollback(self, snapshot: MutationSnapshot) -> bool: ...


MutationAction = Callable[[], Any]


class MutationScope:
    """Execute one bounded mutation and make rollback certainty explicit."""

    def __init__(self, capability: MutationCapability, snapshot: MutationSnapshot) -> None:
        self.capability = capability
        self.snapshot = snapshot
        self.report = ExecutionReport(
            ExecutionPhase.TARGET_RESOLVED,
            "certain",
            RollbackStatus.NOT_ATTEMPTED,
        )
        self._entered = False
        self._finished = False
        self._rollback_attempted = False
        self._rebuild_succeeded = False

    def __enter__(self) -> MutationScope:  # noqa: PYI034
        try:
            self.capability.begin_mutation(self.snapshot)
        except BaseException as exc:
            self.report = self.report.transition(
                ExecutionPhase.FAILED,
                state_certainty="uncertain",
                rollback_status=RollbackStatus.STATE_UNCERTAIN,
            )
            self._finished = True
            self._attach_execution(exc)
            error = TransactionError("mutation scope could not begin")
            error.execution = self.report
            raise error from exc
        self._entered = True
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if exc_value is not None and not self._finished:
            self._fail(exc_value if isinstance(exc_value, BaseException) else Exception())
            return
        if not self._finished:
            self.commit()

    def step(self, label: str, action: MutationAction) -> Any:
        if self._finished or self.report.rollback_status is RollbackStatus.STATE_UNCERTAIN:
            raise TransactionError("mutation scope cannot accept another step")
        try:
            result = action()
            if self.report.phase is ExecutionPhase.TARGET_RESOLVED:
                self.report = self.report.transition(ExecutionPhase.EXECUTED)
        except BaseException as exc:
            self._fail(exc, label=label)
            raise
        else:
            return result

    def mark_created_resource(self, resource_id: str) -> None:
        self.snapshot = replace(
            self.snapshot,
            created_resource=True,
            created_resource_id=resource_id,
        )
        record = getattr(self.capability, "record_created_resource", None)
        if record is not None:
            record(resource_id)

    def rebuild(self, action: MutationAction | None = None) -> Any:
        if action is None:
            action = getattr(self.capability, "rebuild", None)
        if action is None:
            raise TransactionError("mutation capability does not provide rebuild")
        try:
            result = action()
            if not getattr(result, "success", False):
                raise RebuildError(  # noqa: TRY301
                    "SOLIDWORKS rebuild was unsuccessful",
                    details={"errors": tuple(getattr(result, "errors", ()))},
                )
            self.report = self.report.transition(ExecutionPhase.REBUILT)
            self._rebuild_succeeded = True
        except BaseException as exc:
            self._fail(exc, label="rebuild")
            raise
        else:
            return result

    def verify(self, postconditions: Iterable[MutationAction]) -> None:
        try:
            if not self._rebuild_succeeded:
                raise TransactionError(  # noqa: TRY301
                    "mutation scope requires successful rebuild before verification"
                )
            for postcondition in postconditions:
                if not postcondition():
                    raise VerificationError(  # noqa: TRY301
                        "required mutation postcondition failed"
                    )
            self.report = self.report.transition(ExecutionPhase.VERIFIED)
        except BaseException as exc:
            self._fail(exc, label="verification")
            raise

    def commit(self) -> ExecutionReport:
        if self._finished:
            return self.report
        if self.report.phase is not ExecutionPhase.VERIFIED or not self._rebuild_succeeded:
            error = TransactionError(
                "mutation scope requires successful verification before commit"
            )
            self._fail(error, label="commit")
            raise error
        try:
            self.capability.commit_mutation(self.snapshot)
        except BaseException as exc:
            self._fail(exc, label="commit")
            raise
        self.report = self.report.transition(ExecutionPhase.COMMITTED)
        self._finished = True
        return self.report

    def rollback(self) -> ExecutionReport:
        if self._rollback_attempted:
            return self.report
        self._rollback_attempted = True
        try:
            self.capability.rollback_mutation(self.snapshot)
        except BaseException:
            rollback_status = RollbackStatus.ROLLBACK_FAILED
            verified = False
        else:
            try:
                verified = bool(self.capability.verify_rollback(self.snapshot))
            except BaseException:
                rollback_status = RollbackStatus.STATE_UNCERTAIN
                verified = False
            else:
                rollback_status = (
                    RollbackStatus.ROLLED_BACK if verified else RollbackStatus.STATE_UNCERTAIN
                )
        self.report = self.report.transition(
            ExecutionPhase.FAILED,
            state_certainty="certain" if verified else "uncertain",
            rollback_status=rollback_status,
        )
        self._finished = True
        return self.report

    def _fail(self, cause: BaseException, *, label: str | None = None) -> None:
        self.rollback()
        self._attach_execution(cause)
        if self.report.rollback_status in {
            RollbackStatus.ROLLBACK_FAILED,
            RollbackStatus.STATE_UNCERTAIN,
        }:
            error = TransactionError(
                "mutation rollback could not be verified",
                details={"label": label} if label else None,
            )
            error.execution = self.report
            raise error from cause

    def _attach_execution(self, cause: BaseException) -> None:
        if isinstance(cause, CadipyError):
            cause.execution = self.report
        else:
            setattr(cause, "execution", self.report)  # noqa: B010


def snapshot_for_document(
    document: Any,
    *,
    created_resource: bool = False,
    dirty: bool | None = None,
    save_observation: str | None = None,
    model_fingerprint: str | None = None,
) -> MutationSnapshot:
    """Build a snapshot from a serializable document handle."""
    return MutationSnapshot(
        target_identity=DocumentIdentity(
            document_id=document.id,
            path=Path(document.path) if document.path else None,
            title=document.title,
            document_type=document.document_type,
            configuration=document.configuration,
        ),
        dirty=dirty,
        save_observation=save_observation,
        model_fingerprint=model_fingerprint,
        created_resource=created_resource,
    )
