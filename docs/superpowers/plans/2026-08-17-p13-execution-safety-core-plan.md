# P1.3-A Execution Safety Core Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make every CADiPy session execute through one owned STA runtime, enforce typed OpSpec contracts at runtime, make required verification failures explicit operation failures, and provide bounded mutation rollback semantics.

**Architecture:** CadipySession submits semantic commands to an in-process StaExecutorHost. The host owns the executor, dispatcher, target registry, and audit state on one worker thread; callers receive only serializable domain values. Immutable parameter/postcondition schemas, execution reports, and MutationScope provide the shared contract used by Python API, RPC, MCP, CLI, and the current Python COM backend.

**Tech Stack:** Python 3.10–3.13, standard-library threading/queue/dataclasses/enum, pytest, pytest-cov, pywin32 only inside the existing SolidWorks backend, uv, and the existing GitHub self-hosted SolidWorks runner.

**Spec:** docs/superpowers/specs/2026-08-17-p13-execution-safety-core-design.md

## Global Constraints

* No Git worktrees; work in the repository root on a branch created from the current main.
* After each task's gates pass: commit the task, fast-forward merge it into main, run merged-result gates, push main over SSH through 127.0.0.1:12334, delete the task branch, and leave the repository on main.
* Do not create a pull request.
* No new modeling feature family, CLI command, MCP tool, or public COM escape hatch is added in P1.3-A.
* All Python COM calls, executor lifecycle calls, dispatcher calls, target resolution, registry mutation, and audit recording for a session run on one dedicated STA execution thread.
* Public values remain serializable CADiPy domain values; no live COM object crosses a public or host boundary.
* The schema layer uses only the Python standard library and public CADiPy engineering units; it does not introduce Pydantic.
* Required postcondition failure uses stable error code verification_failed and can never produce ok=True.
* A timed-out or ambiguous mutation is state_uncertain; automatic mutation retry is forbidden until session cleanup and reconnection.
* The current 100×60×3 mm SOLIDWORKS round-trip fixture remains a real integration contract and must execute through the host.
* Portable compatibility evidence covers Python 3.10, 3.11, 3.12, and 3.13; real SOLIDWORKS integration runs on Python 3.12.

---

## File and responsibility map

* Create src/cadipy/domain/execution.py for execution phases, rollback statuses, and serializable ExecutionReport values.
* Create src/cadipy/operations/schema.py for immutable ParamType, ParamSpec, PostconditionSpec, and parameter validation helpers.
* Create src/cadipy/runtime/host.py for ExecutorHost, HostState, and StaExecutorHost queue/thread lifecycle.
* Create src/cadipy/runtime/mutation.py for MutationSnapshot, semantic mutation capability, and MutationScope.
* Create src/cadipy/verification/registry.py for postcondition verifier registration and lookup without COM references.
* Modify src/cadipy/domain/errors.py for stable execution, verification, and transaction error codes.
* Modify src/cadipy/protocol/result.py for additive execution report serialization and failure mapping.
* Modify src/cadipy/operations/registry.py for typed OpSpec declarations.
* Modify src/cadipy/operations/dispatch.py for host-confined validation, target-type enforcement, postcondition execution, and mutation integration.
* Modify src/cadipy/session.py and src/cadipy/api.py for session host ownership and the synchronous semantic façade.
* Modify src/cadipy/protocol/server.py, src/cadipy/protocol/mcp.py, and src/cadipy/cli.py so adapters call the session façade rather than a dispatcher directly.
* Modify src/cadipy/backends/executor.py and src/cadipy/backends/solidworks/executor.py for the backend-neutral mutation capability seam.
* Add tests/domain/test_execution.py, tests/operations/test_schema.py, tests/runtime/test_host.py, tests/runtime/test_mutation.py, and strict tests under tests/integration/solidworks.
* Create tests/support/fakes.py for RecordingExecutor, FakeMutationCapability, make_dispatcher_with_spec, REQUIRED_FAILURE_SPEC, and make_request helpers used by portable tests.
* Update docs/usage.md, docs/usage.en.md, docs/protocol.md, docs/protocol.en.md, docs/exceptions.md, docs/exceptions.en.md, docs/ci.md, and docs/ci.en.md.

Portable test support contracts:

* RecordingExecutor records `created_thread_id`, `call_thread_ids`, `disconnect_called`, and operation order; it implements the minimum SolidWorksExecutor methods used by each focused test and returns serializable ApplicationInfo/DocumentHandle values.
* FakeMutationCapability implements `begin_mutation`, `commit_mutation`, `rollback_mutation`, and `verify_rollback`, with constructor flags `rollback_verified: bool = True` and `raise_on_begin: bool = False`.
* `REQUIRED_FAILURE_SPEC` is an OpSpec with one required postcondition named `forced_failure` whose registered verifier returns false.
* `REQUIRED_POSTCONDITIONS` is a tuple containing one required postcondition whose fake verifier returns true.
* `make_dispatcher_with_spec(executor, spec) -> OperationDispatcher` creates a dispatcher using a one-entry test registry and a fake target resolver returning a Part DocumentHandle.
* `make_request(operation) -> dict[str, Any]` returns protocol version 1 with id `test-request`, the supplied operation, empty params, and no target.
* `make_snapshot() -> MutationSnapshot` returns a deterministic Part snapshot with document id `doc-1`, dirty state false, and fingerprint `("empty",)`.
* `recording_factory` and `raising_factory` are callable `RecordingExecutorFactory` instances that expose `created_thread_id`, `host_thread_id`, and the created fake executor for session assertions.
* `raise_forced_failure() -> NoReturn` raises a deterministic RuntimeError for rollback tests.

---

### Task 1: Add execution-state domain values and result reporting

Files:
- Create src/cadipy/domain/execution.py
- Modify src/cadipy/domain/errors.py
- Modify src/cadipy/protocol/result.py
- Modify src/cadipy/protocol/server.py
- Test tests/domain/test_execution.py
- Test tests/protocol/test_adapters.py
- Test tests/test_schema_consistency.py

Interfaces:
- ExecutionPhase, ExecutionReport, and RollbackStatus are serializable domain values.
- OperationResult gains execution: ExecutionReport | None = None and serializes it as an additive protocol version 1 field.
- OperationResult.failure(request_id, operation, error, execution=None) preserves direct Python error propagation while allowing protocol adapters to return structured execution state.
- VerificationError.code becomes verification_failed.

- [ ] Step 1: Write failing domain and serialization tests.

    def test_execution_report_round_trips_to_serializable_values():
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
        assert result.to_dict()["execution"]["phase"] == "committed"

    def test_verification_error_has_stable_failure_code():
        assert VerificationError("failed").code == "verification_failed"

- [ ] Step 2: Run focused tests and verify the new values/field fail.

    uv run pytest tests/domain/test_execution.py tests/protocol/test_adapters.py tests/test_schema_consistency.py -q

Expected: FAIL because the execution values/field and error-code change do not yet exist.

- [ ] Step 3: Implement immutable execution values and the additive result field.

Use Python 3.10-compatible str, Enum values for received, validated, target_resolved, executed, rebuilt, verified, committed, validation_failed, target_failed, execution_failed, rebuild_failed, verification_failed, rollback_attempted, rolled_back, rollback_failed, and state_uncertain. Keep existing serialized result keys and add only execution.

- [ ] Step 4: Run focused error and protocol suites.

    uv run pytest tests/domain/test_execution.py tests/domain/test_errors.py tests/protocol tests/test_schema_consistency.py -q

Expected: PASS.

- [ ] Step 5: Commit and integrate this task.

    git add src/cadipy/domain/execution.py src/cadipy/domain/errors.py src/cadipy/protocol/result.py src/cadipy/protocol/server.py tests
    git commit -m "feat: add execution state reports"
    git switch main
    git merge --ff-only feat/p13-a-execution-state
    uv run pytest tests/domain tests/protocol tests/test_schema_consistency.py -q
    git push origin main
    git branch -d feat/p13-a-execution-state

---

### Task 2: Replace untyped OpSpec parameters with immutable schemas

Files:
- Create src/cadipy/operations/schema.py
- Modify src/cadipy/operations/registry.py
- Modify src/cadipy/operations/dispatch.py
- Create tests/operations/test_schema.py
- Modify tests/operations/test_registry.py
- Modify tests/test_schema_consistency.py

Interfaces:
- ParamType(str, Enum) exposes BOOLEAN, INTEGER, NUMBER, STRING, PATH, OBJECT, and ARRAY.
- ParamSpec is frozen and contains type, required, default, unit, finite, numeric bounds, and string choices.
- PostconditionSpec is frozen and contains name, required, and optional verifier.
- OpSpec.parameters becomes Mapping[str, ParamSpec]; OpSpec exposes target_document_types, result_document_types, and typed postconditions.
- validate_parameters(spec, params) -> dict[str, Any] rejects unknown keys, missing required values, invalid primitive types, non-finite numbers, out-of-range numbers, and invalid choices before executor calls.

- [ ] Step 1: Write failing validation tests for every boundary rule.

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_finite_number_rejects_non_finite_values(value):
        spec = ParamSpec(type=ParamType.NUMBER, required=True, finite=True)
        with pytest.raises(InvalidArgumentError):
            validate_parameter("depth_mm", spec, value, operation="part.test")

    def test_boolean_is_not_accepted_as_number():
        spec = ParamSpec(type=ParamType.NUMBER, required=True)
        with pytest.raises(InvalidArgumentError):
            validate_parameter("depth_mm", spec, True, operation="part.test")

    def test_numeric_bounds_and_choices_are_enforced():
        minimum = ParamSpec(type=ParamType.NUMBER, exclusive_minimum=0.0)
        with pytest.raises(InvalidArgumentError):
            validate_parameter("radius_mm", minimum, 0.0, operation="part.test")
        choices = ParamSpec(type=ParamType.STRING, choices=frozenset({"front", "top"}))
        with pytest.raises(InvalidArgumentError):
            validate_parameter("plane", choices, "right", operation="sketch.create")

- [ ] Step 2: Run focused schema tests and verify failure.

    uv run pytest tests/operations/test_schema.py tests/operations/test_registry.py -q

Expected: FAIL because typed declarations and centralized validation are not implemented.

- [ ] Step 3: Implement immutable declarations and centralized validation.

Use a private _MISSING sentinel so a default of None remains distinguishable from no default. Public dimensions remain plain numbers in the declared unit; unit="mm" documents the contract and does not accept arbitrary unit-bearing objects.

Migrate current registry declarations to explicit ParamSpec values. Use target_document_types for resolved target checks and result_document_types for targetless create/open operations. Keep registry serialization JSON-compatible.

- [ ] Step 4: Add document-type and schema serialization tests.

    def test_part_operation_rejects_assembly_target(fake_dispatcher, assembly_handle):
        with pytest.raises(DocumentTypeError):
            fake_dispatcher.dispatch({
                "id": "r-1",
                "operation": "part.rebuild",
                "params": {},
                "target": {"document_id": assembly_handle.id},
            })

Also assert that OpSpec.to_dict() is JSON-compatible and that MCP/RPC/CLI exposure derives the same parameter names.

- [ ] Step 5: Run focused and portable suites.

    uv run pytest tests/operations tests/protocol tests/test_schema_consistency.py -q
    uv run pytest tests -m "not real_solidworks" -q

Expected: PASS with no real-SW tests executed by the portable command.

- [ ] Step 6: Commit and integrate this task.

    git add src/cadipy/operations/schema.py src/cadipy/operations/registry.py src/cadipy/operations/dispatch.py tests
    git commit -m "feat: enforce typed operation schemas"
    git switch main
    git merge --ff-only feat/p13-a-typed-schema
    uv run ruff check .
    uv run pytest tests -m "not real_solidworks" -q
    git push origin main
    git branch -d feat/p13-a-typed-schema

---

### Task 3: Implement the dedicated STA ExecutorHost

Files:
- Create src/cadipy/runtime/host.py
- Create tests/runtime/test_host.py
- Modify tests/runtime/test_session.py for host lifecycle fixtures

Interfaces:
- HostState(str, Enum) exposes CREATED, RUNNING, CLOSING, CLOSED, and FAILED.
- ExecutorHost exposes start(), submit(command, timeout=None), and close(timeout=30.0).
- StaExecutorHost(executor_factory, command_timeout=None) constructs the executor on its worker thread and exposes no live backend object.
- Submitted callables execute FIFO; their return values or exceptions are delivered to the caller.

- [ ] Step 1: Write failing host tests using a semantic fake executor.

    def test_host_serializes_commands_on_one_worker_thread():
        host = StaExecutorHost(lambda: RecordingExecutor())
        host.start()
        try:
            thread_ids = [host.submit(lambda: threading.get_ident()) for _ in range(3)]
            assert len(set(thread_ids)) == 1
        finally:
            host.close(timeout=30.0)

    def test_host_rejects_commands_after_close():
        host = StaExecutorHost(lambda: RecordingExecutor())
        host.start()
        host.close(timeout=30.0)
        with pytest.raises(SessionClosedError):
            host.submit(lambda: None)

- [ ] Step 2: Add FIFO, worker-failure, timeout, queue-drain, and re-entrancy tests.

Prove command order, worker failure transition, timeout behavior without interrupting the callable, rejection of queued commands after failure, normal close ordering, and no deadlock for a command submitted from the worker thread.

- [ ] Step 3: Run focused host tests and verify failure.

    uv run pytest tests/runtime/test_host.py -q

Expected: FAIL because the host module and lifecycle do not yet exist.

- [ ] Step 4: Implement the queue and thread lifecycle.

Use queue.Queue, a worker Thread, and per-command Future/event completion. The worker creates the executor from executor_factory after the backend initializes STA. Normal close transitions to CLOSING, rejects new submissions, enqueues a sentinel after accepted work, invokes semantic disconnect before the sentinel, and joins with a 30-second default. A command timeout does not kill the worker; it marks the host failed and rejects subsequent work.

- [ ] Step 5: Run host and runtime tests.

    uv run pytest tests/runtime/test_host.py tests/runtime/test_session.py -q

Expected: PASS without importing pythoncom or requiring SOLIDWORKS.

- [ ] Step 6: Commit and integrate this task.

    git add src/cadipy/runtime/host.py tests/runtime/test_host.py tests/runtime/test_session.py
    git commit -m "feat: add serialized execution host"
    git switch main
    git merge --ff-only feat/p13-a-executor-host
    uv run ruff format --check .
    uv run pytest tests/runtime tests -m "not real_solidworks" -q
    git push origin main
    git branch -d feat/p13-a-executor-host

---

### Task 4: Route sessions and adapters through the host

Files:
- Modify src/cadipy/session.py
- Modify src/cadipy/api.py
- Modify src/cadipy/protocol/server.py
- Modify src/cadipy/protocol/mcp.py
- Modify src/cadipy/cli.py only where it calls a dispatcher directly
- Modify tests/runtime/test_session.py
- Modify tests/protocol/test_adapters.py
- Modify tests/test_schema_consistency.py

Interfaces:
- CadipySession owns a StaExecutorHost; production sessions pass a factory that creates PythonComSolidWorksExecutor on the host thread.
- CadipySession.__enter__ starts the host and submits attach/launch.
- CadipySession.execute(operation, params, target, request_id) -> OperationResult submits one dispatcher command and returns only serialized result/domain values.
- CadipySession.__exit__ always submits disconnect/cleanup in finally, then closes and joins the host.
- CadipySession.dispatch_request(request: Mapping[str, Any]) -> OperationResult submits a raw protocol request to the host-confined dispatcher.
- ProtocolServer.from_session(session) stores the session façade and calls session.dispatch_request; McpAdapter follows the same route and never calls a raw dispatcher from a transport thread.

- [ ] Step 1: Write failing session tests for thread confinement and cleanup.

    def test_session_constructs_executor_and_dispatcher_on_host_thread():
        session = CadipySession(executor_factory=recording_factory)
        with session:
            result = session.execute("application.info")
        assert recording_factory.created_thread_id == recording_factory.host_thread_id
        assert result.ok is True

    def test_session_exit_disconnects_when_dispatch_raises():
        session = CadipySession(executor_factory=raising_factory)
        with pytest.raises(CadipyError):
            with session:
                session.execute("application.info")
        assert raising_factory.created_executor.disconnect_called is True

Replace the old test assertion that server.dispatcher is session.dispatcher with `assert session.server.session is session`; the adapter must be checked as a façade, not by sharing a mutable dispatcher object.

- [ ] Step 2: Add adapter concurrency tests.

Submit requests concurrently through the session protocol server. Assert all fake executor calls share one thread ID, operations preserve FIFO submission order, and no adapter retains a direct dispatcher reference that can bypass the host.

- [ ] Step 3: Run focused tests and verify failure.

    uv run pytest tests/runtime/test_session.py tests/protocol/test_adapters.py -q

Expected: FAIL because current sessions and adapters call the dispatcher directly.

- [ ] Step 4: Integrate host ownership into CadipySession.

Move mutable registry, dispatcher, and audit initialization into host startup. Keep create_part, list_documents, inspect, rebuild, connect, and launch public semantics unchanged. Ensure __exit__ does not close an attached user-owned SOLIDWORKS instance.

- [ ] Step 5: Route protocol adapters through the session façade and update schema tests.

Keep one operation registry and one OperationResult shape. Protocol adapters may catch and serialize typed errors, but they must not invoke the backend or dispatcher directly.

- [ ] Step 6: Run portable quality gates.

    uv run ruff format --check .
    uv run ruff check .
    uv run mypy src/cadipy
    uv run pytest tests -m "not real_solidworks" -q

- [ ] Step 7: Commit and integrate this task.

    git add src/cadipy/session.py src/cadipy/api.py src/cadipy/protocol src/cadipy/cli.py tests
    git commit -m "feat: confine sessions to execution host"
    git switch main
    git merge --ff-only feat/p13-a-session-host-routing
    uv run pytest tests -m "not real_solidworks" -q
    git push origin main
    git branch -d feat/p13-a-session-host-routing

---

### Task 5: Enforce postconditions and lifecycle reports in dispatch

Files:
- Create src/cadipy/verification/registry.py
- Modify src/cadipy/operations/dispatch.py
- Modify src/cadipy/verification/postconditions.py
- Modify src/cadipy/protocol/result.py and src/cadipy/protocol/server.py as required
- Create tests/verification/test_registry.py
- Modify tests/operations/test_dispatch.py
- Modify tests/protocol/test_adapters.py

Interfaces:
- register_postcondition(name, verifier) registers a pure semantic verifier once.
- verify_postconditions(specs, operation_data, inspection) -> None raises VerificationError on required failure.
- OperationDispatcher records lifecycle phases and returns a committed execution report only after required verification.
- Known dispatch failures carry the last phase and ExecutionReport; protocol adapters serialize ok=False.

- [ ] Step 1: Write failing required-verification tests.

    def test_required_verification_failure_cannot_return_ok_true():
        fake_executor = RecordingExecutor()
        dispatcher = make_dispatcher_with_spec(fake_executor, REQUIRED_FAILURE_SPEC)
        result = ProtocolServer(dispatcher).handle(make_request(REQUIRED_FAILURE_SPEC.name))
        assert result["ok"] is False
        assert result["error"]["code"] == "verification_failed"
        assert result["execution"]["phase"] == "verification_failed"

Also test that optional failed observations remain successful data while required failures do not.

- [ ] Step 2: Run focused tests and verify the current false-success behavior.

    uv run pytest tests/operations/test_dispatch.py tests/protocol/test_adapters.py -q

Expected: FAIL for the new required-failure assertions.

- [ ] Step 3: Implement the verifier registry and phase tracking.

Register existing rectangular, rebuild, entity, relation, and dimension postconditions by stable names. Move required verification into one dispatcher path; remove the composite shape in which ok=True contains verification="failed".

- [ ] Step 4: Implement failure serialization while preserving direct Python error convention.

Direct Python callers continue to receive typed CadipyError where current API behavior requires it. RPC, MCP, and CLI adapters return OperationResult.failure with ok=False, stable code, and execution report. Do not expose traceback or raw COM values in this task.

- [ ] Step 5: Run dispatch, verification, protocol, and schema tests.

    uv run pytest tests/operations tests/verification tests/protocol tests/test_schema_consistency.py -q

- [ ] Step 6: Commit and integrate this task.

    git add src/cadipy/verification src/cadipy/operations/dispatch.py src/cadipy/protocol tests
    git commit -m "feat: enforce required postconditions"
    git switch main
    git merge --ff-only feat/p13-a-postcondition-runtime
    uv run pytest tests -m "not real_solidworks" -q
    git push origin main
    git branch -d feat/p13-a-postcondition-runtime

---

### Task 6: Add bounded MutationScope and rollback capability

Files:
- Create src/cadipy/runtime/mutation.py
- Modify src/cadipy/backends/executor.py
- Modify src/cadipy/backends/solidworks/executor.py
- Modify src/cadipy/operations/dispatch.py
- Create tests/runtime/test_mutation.py
- Modify tests/backends/test_executor_contract.py
- Modify tests/operations/test_dispatch.py

Interfaces:
- MutationSnapshot contains target identity, dirty/save observation, optional model fingerprint, and created-resource marker.
- MutationCapability exposes begin_mutation, commit_mutation, rollback_mutation, and verify_rollback using semantic values only.
- MutationScope exposes step(label, action), rebuild, verify, commit, and rollback; it returns an ExecutionReport or raises a typed failure.
- PythonComSolidWorksExecutor maps this seam to SOLIDWORKS undo recording where supported and owned-document cleanup for a Part created inside the rectangular composite.

- [ ] Step 1: Write failing state-machine tests.

    def test_mutation_scope_commits_after_rebuild_and_verification():
        scope = MutationScope(FakeMutationCapability(), make_snapshot())
        with scope:
            scope.step("create sketch", lambda: None)
            scope.rebuild()
            scope.verify(REQUIRED_POSTCONDITIONS)
        assert scope.report.phase is ExecutionPhase.COMMITTED

    def test_mutation_scope_reports_rollback_failure_without_success():
        capability = FakeMutationCapability(rollback_verified=False)
        scope = MutationScope(capability, make_snapshot())
        with pytest.raises(TransactionError):
            with scope:
                scope.step("forced failure", raise_forced_failure)
        assert scope.report.state_certainty == "uncertain"

- [ ] Step 2: Add created-resource and existing-target snapshot tests.

Assert rollback of a new Part requests owned-document cleanup, while rollback of an existing target uses the captured semantic fingerprint and never closes a user-owned document.

- [ ] Step 3: Run mutation tests and verify failure.

    uv run pytest tests/runtime/test_mutation.py tests/backends/test_executor_contract.py -q

Expected: FAIL because no mutation scope or capability seam exists.

- [ ] Step 4: Implement the pure MutationScope state machine.

Make one rollback attempt after a failed step, rebuild, or required verification. If rollback is ambiguous, mark STATE_UNCERTAIN, reject subsequent mutation through the host, and do not retry the failed action. Do not claim ACID, crash-safe, or exactly-once semantics.

- [ ] Step 5: Implement the Python COM semantic capability.

Keep SOLIDWORKS undo method calls inside backends/solidworks. Expose only semantic mutation capability to runtime and operations. When the composite creates a new document, record ownership and close only that CADiPy-owned document on rollback.

- [ ] Step 6: Wrap part.create_rectangular_extrude in MutationScope.

The operation creates the Part, Sketch, rectangle, and extrusion inside one scope; rebuilds and verifies before commit; returns a committed execution report on success; and returns failure with rollback status on any required failure.

- [ ] Step 7: Run portable mutation and composite tests.

    uv run pytest tests/runtime/test_mutation.py tests/operations/test_dispatch.py tests/backends -q

- [ ] Step 8: Commit and integrate this task.

    git add src/cadipy/runtime/mutation.py src/cadipy/backends src/cadipy/operations/dispatch.py tests
    git commit -m "feat: add bounded mutation rollback"
    git switch main
    git merge --ff-only feat/p13-a-mutation-scope
    uv run pytest tests -m "not real_solidworks" -q
    git push origin main
    git branch -d feat/p13-a-mutation-scope

---

### Task 7: Add strict real-SOLIDWORKS host and failure evidence

Files:
- Modify tests/integration/solidworks/conftest.py
- Create tests/integration/solidworks/test_execution_host.py
- Create tests/integration/solidworks/test_required_verification_failure.py
- Modify tests/integration/solidworks/test_part_extrude_roundtrip.py
- Modify tests/integration/solidworks/test_parametric_sketch_roundtrip.py
- Modify tests/integration/solidworks/test_session_target_race.py
- Modify tests/integration/solidworks/test_application_visibility.py
- Modify .github/workflows/solidworks-tests.yml to keep the strict suite as one serial job with preflight and cleanup

Interfaces:
- Strict fixtures invoke the public session API and never use live COM objects in assertions.
- CADIPY_REQUIRE_REAL_SOLIDWORKS=1 remains fail-fast for unavailable or incompatible SOLIDWORKS.
- Preflight continues to reject a process that predates the job; the user-owned lifecycle test creates its attached instance after preflight and verifies CADiPy does not terminate it.

- [ ] Step 1: Write strict tests for host confinement and round-trip routing.

    @pytest.mark.real_solidworks
    def test_roundtrip_executes_through_one_sta_session(solidworks_session, tmp_path):
        result = run_rectangular_contract_via_session(solidworks_session, tmp_path)
        assert result.ok is True
        assert result.execution["phase"] == "committed"

Use the existing 100×60×3 mm fixture and expose thread identity only through a diagnostic domain value or test-only semantic executor hook; never return a COM object.

Define `run_rectangular_contract_via_session(session, tmp_path) -> OperationResult` in `test_part_extrude_roundtrip.py`. It must create the Part, Sketch, 100×60 mm rectangle, and 3 mm extrusion through session operations, rebuild and inspect through the same session, save to `tmp_path`, close, reopen, and verify the postconditions after reopen.

- [ ] Step 2: Add strict verification-failure and ownership tests.

Create a controlled failed postcondition through a test-only semantic verification seam, assert ok=False and verification_failed, and assert an attached user-owned application remains available after CADiPy disconnect. Do not use taskkill, global process cleanup, or silent skip in strict mode.

Migrate the existing integration tests from direct solidworks_executor calls to the solidworks_session façade. Replace the current fixture's preconstructed executor with an executor factory so COM acquisition and all handle registries are created on the STA host thread. Keep the existing preflight/revision checks and temporary-file cleanup.

- [ ] Step 3: Run strict tests serially on the registered runner.

    $env:CADIPY_REQUIRE_REAL_SOLIDWORKS="1"
    uv run pytest tests/integration/solidworks -m real_solidworks -q
    Remove-Item Env:CADIPY_REQUIRE_REAL_SOLIDWORKS

Expected: PASS with the round-trip and host/ownership evidence. Run local preflight and pytest serially; never launch two SOLIDWORKS COM sessions concurrently.

- [ ] Step 4: Run the strict GitHub workflow and inspect logs.

    gh run list --repo Zn070515/CADiPy --workflow CI --limit 1
    $runId = gh run list --repo Zn070515/CADiPy --workflow CI --limit 1 --json databaseId --jq '.[0].databaseId'
    gh run view $runId --repo Zn070515/CADiPy --log

Required evidence includes Runner: CADiPy-SolidWorks, Revision 34.3.2, strict integration pass count, and cleanup pass.

- [ ] Step 5: Commit and integrate this task.

    git add tests/integration/solidworks .github/workflows/solidworks-tests.yml
    git commit -m "test: verify strict execution safety on SolidWorks"
    git switch main
    git merge --ff-only feat/p13-a-real-solidworks-safety
    git push origin main
    git branch -d feat/p13-a-real-solidworks-safety

---

### Task 8: Document the runtime contract and close P1.3-A gates

Files:
- Modify docs/usage.md
- Modify docs/usage.en.md
- Modify docs/protocol.md
- Modify docs/protocol.en.md
- Modify docs/exceptions.md
- Modify docs/exceptions.en.md
- Modify docs/ci.md
- Modify docs/ci.en.md
- Inspect mkdocs.yml and update navigation only when the changed public pages are not already reachable from the existing nav

Interfaces:
- Documentation states one STA execution thread per session, synchronous façade semantics, failure result phases, rollback/uncertain-state behavior, and no ACID/exactly-once claim.
- Documentation distinguishes portable fake-executor tests from strict real-SOLIDWORKS tests.
- No version bump is made for this implementation stage.

- [ ] Step 1: Update usage and protocol examples.

    with cadipy.launch(visible=False) as cad:
        result = cad.execute(
            "part.create_rectangular_extrude",
            params={
                "plane": "Front Plane",
                "width_mm": 100.0,
                "height_mm": 60.0,
                "depth_mm": 3.0,
            },
        )
        if not result.ok:
            raise RuntimeError(result.error)

Explain that concurrent callers are serialized, a timeout does not cancel a running COM call, and uncertain state requires reconnection before mutation. The example uses the exact 100×60×3 mm contract parameters.

- [ ] Step 2: Update exception and CI documentation.

Document verification_failed, state_uncertain, rollback statuses, host ownership, strict mode, runner labels, and the rule that pre-existing SOLIDWORKS processes are not terminated.

- [ ] Step 3: Run complete local gates.

    uv run ruff format --check .
    uv run ruff check .
    uv run mypy src/cadipy
    uv run pytest tests -m "not real_solidworks" --cov=cadipy.domain --cov=cadipy.operations --cov=cadipy.protocol --cov=cadipy.verification --cov=cadipy.diagnostics --cov=cadipy.audit --cov-report=term-missing --cov-fail-under=85 -q
    uv run mkdocs build --strict
    uv build

Expected: all commands exit 0 and portable coverage remains at least 85% for the configured pure modules.

- [ ] Step 4: Run final strict real-SW verification.

    $env:CADIPY_REQUIRE_REAL_SOLIDWORKS="1"
    uv run pytest tests/integration/solidworks -m real_solidworks -q
    Remove-Item Env:CADIPY_REQUIRE_REAL_SOLIDWORKS

Expected: all strict integration tests pass, including round-trip, host confinement, required-verification failure, and ownership cleanup evidence.

- [ ] Step 5: Review the final diff and commit documentation.

    git diff --check
    git status --short
    git diff --stat origin/main...HEAD
    git commit -m "docs: document execution safety guarantees"

The review must confirm no generated CAD files, credentials, private paths, COM reprs, or untracked runner artifacts entered the repository.

- [ ] Step 6: Integrate the final task directly into main.

    git switch main
    git merge --ff-only feat/p13-a-runtime-documentation
    git push origin main
    git branch -d feat/p13-a-runtime-documentation
    git status --short --branch

Expected final state: clean main, main equals origin/main, no local task branch, no PR, portable gates green, and strict real-SOLIDWORKS evidence recorded in the CI run.

---

## Plan self-review checklist

Before implementation begins, verify this plan against the spec:

* Public compatibility and non-goals are enforced by Tasks 1, 4, and 8: additive protocol version 1 reporting, unchanged session factories, no new modeling family, and no version bump.
* Pure Python tests are specified in Tasks 1–6 and remain independent of COM; Real-SOLIDWORKS host evidence is specified in Task 7.
* Acceptance criteria are the final merged-result gates in Task 8 plus the explicit H0–H3 checks below.
* H0 is covered by Tasks 3–4 and strict host tests in Task 7.
* H1 is covered by Task 2, including target/result document-type enforcement, finite numeric validation, choices, and schema consistency.
* H2 is covered by Tasks 1 and 5, including required postcondition failure and verification_failed serialization.
* H3 is covered by Task 6, including snapshots, undo capability, rollback status, and state_uncertain behavior.
* COM ownership, user-owned process safety, session teardown, and no mid-command cancellation are covered by Tasks 3, 4, 6, and 7.
* Pure tests, strict real-SOLIDWORKS tests, Python compatibility, coverage, docs, and package gates are covered by Tasks 1–8.
* No task introduces a new modeling feature family or a second protocol/operation definition.
* The plan uses only defined names: ExecutorHost, StaExecutorHost, HostState, ExecutionPhase, ExecutionReport, ParamType, ParamSpec, PostconditionSpec, MutationSnapshot, MutationCapability, and MutationScope.
