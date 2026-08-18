from __future__ import annotations

from dataclasses import dataclass

import pytest

from cadipy.backends.executor import RebuildReport
from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import RebuildError, TransactionError
from cadipy.domain.execution import ExecutionPhase, RollbackStatus
from cadipy.domain.identities import DocumentIdentity
from cadipy.runtime.mutation import MutationScope, MutationSnapshot


def make_snapshot(*, created_resource: bool = False) -> MutationSnapshot:
    return MutationSnapshot(
        target_identity=DocumentIdentity(
            document_id="part-1",
            path=None,
            title="Part1",
            document_type=DocumentType.PART,
        ),
        dirty=False,
        save_observation="saved",
        model_fingerprint="before",
        created_resource=created_resource,
    )


@dataclass
class FakeMutationCapability:
    rollback_verified: bool = True
    fail_rollback: bool = False
    raise_on_verify: bool = False
    fail_begin: bool = False
    fail_commit: bool = False

    def __post_init__(self) -> None:
        self.calls: list[str] = []

    def begin_mutation(self, snapshot: MutationSnapshot) -> None:
        if self.fail_begin:
            raise RuntimeError("begin failed")
        self.calls.append("begin")

    def commit_mutation(self, snapshot: MutationSnapshot) -> None:
        self.calls.append("commit")
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback_mutation(self, snapshot: MutationSnapshot) -> None:
        self.calls.append("rollback")
        if self.fail_rollback:
            raise RuntimeError("rollback failed")

    def verify_rollback(self, snapshot: MutationSnapshot) -> bool:
        self.calls.append("verify_rollback")
        if self.raise_on_verify:
            raise RuntimeError("rollback verification unavailable")
        return self.rollback_verified

    def rebuild(self) -> RebuildReport:
        self.calls.append("rebuild")
        return RebuildReport(success=True)


def test_mutation_scope_commits_after_rebuild_and_verification() -> None:
    capability = FakeMutationCapability()
    scope = MutationScope(capability, make_snapshot())
    with scope:
        scope.step("create sketch", lambda: None)
        scope.rebuild()
        scope.verify((lambda: True,))

    assert scope.report.phase is ExecutionPhase.COMMITTED
    assert scope.report.rollback_status is RollbackStatus.NOT_ATTEMPTED
    assert capability.calls == ["begin", "rebuild", "commit"]


def test_mutation_scope_reports_begin_failure_without_mutating() -> None:
    capability = FakeMutationCapability(fail_begin=True)
    scope = MutationScope(capability, make_snapshot())

    with pytest.raises(TransactionError) as caught:
        scope.__enter__()

    assert caught.value.execution is scope.report
    assert caught.value.__cause__.execution is scope.report
    assert scope.report.phase is ExecutionPhase.FAILED
    assert scope.report.state_certainty == "uncertain"
    assert scope.report.rollback_status is RollbackStatus.STATE_UNCERTAIN
    assert capability.calls == []


def test_mutation_scope_rolls_back_after_commit_failure() -> None:
    capability = FakeMutationCapability(fail_commit=True)
    scope = MutationScope(capability, make_snapshot())

    with pytest.raises(RuntimeError) as caught, scope:
        scope.step("create feature", lambda: None)
        scope.rebuild()
        scope.verify((lambda: True,))

    assert scope.report.phase is ExecutionPhase.FAILED
    assert scope.report.rollback_status is RollbackStatus.ROLLED_BACK
    assert caught.value.execution is scope.report
    assert capability.calls == ["begin", "rebuild", "commit", "rollback", "verify_rollback"]


def test_mutation_scope_reports_rollback_failure_without_success() -> None:
    capability = FakeMutationCapability(rollback_verified=False)
    scope = MutationScope(capability, make_snapshot())
    with pytest.raises(TransactionError), scope:
        scope.step("forced failure", lambda: (_ for _ in ()).throw(ValueError("forced")))

    assert scope.report.phase is ExecutionPhase.FAILED
    assert scope.report.state_certainty == "uncertain"
    assert scope.report.rollback_status is RollbackStatus.STATE_UNCERTAIN
    assert capability.calls == ["begin", "rollback", "verify_rollback"]


def test_mutation_scope_reports_failed_rollback_as_typed_failure() -> None:
    capability = FakeMutationCapability(fail_rollback=True)
    scope = MutationScope(capability, make_snapshot())

    with pytest.raises(TransactionError) as caught, scope:
        scope.step("forced failure", lambda: (_ for _ in ()).throw(ValueError("forced")))

    assert scope.report.phase is ExecutionPhase.FAILED
    assert scope.report.state_certainty == "uncertain"
    assert scope.report.rollback_status is RollbackStatus.ROLLBACK_FAILED
    assert caught.value.execution is scope.report
    assert capability.calls == ["begin", "rollback"]


def test_mutation_scope_reports_verification_exception_as_uncertain_state() -> None:
    capability = FakeMutationCapability(raise_on_verify=True)
    scope = MutationScope(capability, make_snapshot())

    with pytest.raises(TransactionError), scope:
        scope.step("forced failure", lambda: (_ for _ in ()).throw(ValueError("forced")))

    assert scope.report.rollback_status is RollbackStatus.STATE_UNCERTAIN
    assert capability.calls == ["begin", "rollback", "verify_rollback"]


def test_mutation_scope_does_not_retry_after_uncertain_rollback() -> None:
    capability = FakeMutationCapability(rollback_verified=False)
    scope = MutationScope(capability, make_snapshot())

    with pytest.raises(TransactionError), scope:
        scope.step("forced failure", lambda: (_ for _ in ()).throw(ValueError("forced")))

    with pytest.raises(TransactionError, match="cannot accept another step"):
        scope.step("must not retry", lambda: None)

    assert capability.calls == ["begin", "rollback", "verify_rollback"]


def test_mutation_scope_rejects_verification_before_rebuild() -> None:
    capability = FakeMutationCapability()
    snapshot = make_snapshot(created_resource=True)
    scope = MutationScope(capability, snapshot)

    postconditions_called = False

    def postcondition() -> bool:
        nonlocal postconditions_called
        postconditions_called = True
        return True

    with pytest.raises(TransactionError), scope:
        scope.step("create part", lambda: None)
        scope.verify((postcondition,))

    assert scope.report.phase is ExecutionPhase.FAILED
    assert scope.report.rollback_status is RollbackStatus.ROLLED_BACK
    assert postconditions_called is False
    assert capability.calls == ["begin", "rollback", "verify_rollback"]


def test_unsuccessful_rebuild_rolls_back_before_verification_or_commit() -> None:
    capability = FakeMutationCapability()
    scope = MutationScope(capability, make_snapshot())

    with pytest.raises(RebuildError) as caught, scope:
        scope.step("create feature", lambda: None)
        scope.rebuild(lambda: type("Rebuild", (), {"success": False})())

    assert caught.value.execution is scope.report
    assert scope.report.rollback_status is RollbackStatus.ROLLED_BACK
    assert capability.calls == ["begin", "rollback", "verify_rollback"]
