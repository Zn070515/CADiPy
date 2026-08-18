from __future__ import annotations

from dataclasses import dataclass

import pytest

from cadipy.domain.documents import DocumentType
from cadipy.domain.errors import TransactionError
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

    def __post_init__(self) -> None:
        self.calls: list[str] = []

    def begin_mutation(self, snapshot: MutationSnapshot) -> None:
        self.calls.append("begin")

    def commit_mutation(self, snapshot: MutationSnapshot) -> None:
        self.calls.append("commit")

    def rollback_mutation(self, snapshot: MutationSnapshot) -> None:
        self.calls.append("rollback")
        if self.fail_rollback:
            raise RuntimeError("rollback failed")

    def verify_rollback(self, snapshot: MutationSnapshot) -> bool:
        self.calls.append("verify_rollback")
        return self.rollback_verified

    def rebuild(self) -> None:
        self.calls.append("rebuild")


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

    with pytest.raises(TransactionError), scope:
        scope.step("forced failure", lambda: (_ for _ in ()).throw(ValueError("forced")))

    assert scope.report.phase is ExecutionPhase.FAILED
    assert scope.report.state_certainty == "uncertain"
    assert scope.report.rollback_status is RollbackStatus.ROLLBACK_FAILED
    assert capability.calls == ["begin", "rollback"]


def test_mutation_scope_does_not_retry_after_uncertain_rollback() -> None:
    capability = FakeMutationCapability(rollback_verified=False)
    scope = MutationScope(capability, make_snapshot())

    with pytest.raises(TransactionError), scope:
        scope.step("forced failure", lambda: (_ for _ in ()).throw(ValueError("forced")))

    with pytest.raises(TransactionError, match="cannot accept another step"):
        scope.step("must not retry", lambda: None)

    assert capability.calls == ["begin", "rollback", "verify_rollback"]


def test_new_resource_snapshot_is_available_to_capability() -> None:
    capability = FakeMutationCapability()
    snapshot = make_snapshot(created_resource=True)
    scope = MutationScope(capability, snapshot)

    with scope:
        scope.step("create part", lambda: None)
        scope.verify((lambda: True,))
        scope.commit()

    assert snapshot.created_resource is True
