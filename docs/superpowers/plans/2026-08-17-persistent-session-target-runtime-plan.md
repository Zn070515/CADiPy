# Persistent CAD Session & Live Target Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, backend-neutral CADiPy session with explicit SOLIDWORKS attach/launch lifecycle, live document registry, and resolve-once target execution.

**Architecture:** Extend the existing `SolidWorksExecutor` semantic port with application lifecycle and document discovery methods. Add a session-owned `DocumentRegistry`/resolver and route Python, RPC, and MCP through the session's single `OperationDispatcher`; keep COM references private to the Python backend and preserve the existing one-shot API.

**Tech Stack:** Python 3.10–3.13 portable code, Python 3.12 real SOLIDWORKS COM, `uv`, pytest, dataclasses, existing OpSpec registry, existing audit and protocol adapters.

**Spec:** `docs/superpowers/specs/2026-08-17-persistent-session-target-runtime-design.md`

## Global Constraints

- All feature work is on `feat/persistent-session-target-runtime`, directly in the repository root; do not use Git worktrees.
- Public APIs and results contain serializable CADiPy values only; no COM objects.
- `document_id` is session-local and opaque; saved documents can be re-resolved by explicit identity criteria.
- `attach()` never terminates an existing SOLIDWORKS process; only an explicitly launched owned instance may be exited.
- Every target-bound operation resolves exactly once before backend invocation.
- Python, RPC, and MCP consume `OPERATION_REGISTRY`; no adapter-specific operation definitions.
- No new geometry, sketch, feature, assembly, or C# implementation is included.
- Public engineering units remain millimetres/degrees; backend conversion remains centralized.
- Existing rectangular extrusion real-SOLIDWORKS fixture remains a required regression contract.

## File Map

- Create `src/cadipy/session.py`: session lifecycle, session-owned dispatcher, typed convenience methods, and protocol adapter access.
- Create `src/cadipy/runtime.py`: session-local document registry and target resolver implementation.
- Modify `src/cadipy/backends/executor.py`: serializable application/document values and the backend-neutral lifecycle/discovery port.
- Modify `src/cadipy/backends/solidworks/application.py`: explicit attach and launch COM acquisition plus ownership-safe shutdown.
- Modify `src/cadipy/backends/solidworks/documents.py`: enumerate live documents and open requested document types.
- Modify `src/cadipy/backends/solidworks/executor.py`: registry reconciliation, active/open/list/info lifecycle, and session invalidation.
- Modify `src/cadipy/operations/dispatch.py`: document type target parsing and handlers for lifecycle/document operations.
- Modify `src/cadipy/operations/registry.py`: authoritative P0 operation contracts.
- Modify `src/cadipy/api.py` and `src/cadipy/__init__.py`: `connect`, `launch`, and one-shot compatibility routing.
- Modify `src/cadipy/protocol/server.py`: construct a server from a session without creating a second dispatcher.
- Modify `src/cadipy/domain/errors.py`: session lifecycle error.
- Add `tests/runtime/test_session.py`: pure session ownership, resolver, and adapter sharing tests.
- Add `tests/runtime/test_registry.py`: pure registry reconciliation and target matching tests.
- Modify `tests/operations/test_dispatch.py`, `tests/backends/test_executor_contract.py`, and protocol tests: new port methods and operation handlers.
- Add `tests/integration/solidworks/test_session_target_race.py`: real target-race and cleanup contract.
- Modify `tests/integration/solidworks/conftest.py`: session fixture and owned-document cleanup helpers.
- Modify `docs/usage.md`, `docs/usage.en.md`, `docs/protocol.md`, `docs/protocol.en.md`, `docs/api/index.md`, and English counterparts: public session and target semantics.

### Task 1: Lock the serializable session and registry contracts with failing pure tests

**Files:**
- Create: `tests/runtime/test_registry.py`
- Create: `tests/runtime/test_session.py`
- Modify: `tests/conftest.py` only if the runtime test package needs shared pure fixtures.

**Interfaces:**
- Tests consume the planned `DocumentRegistry`, `CadipySession`, `SessionClosedError`, and `SolidWorksExecutor` lifecycle signatures.
- Tests produce the behavioral contract for implementation tasks: one resolver, one dispatcher, and no backend call after session close.

- [ ] **Step 1: Write failing registry tests**

```python
def test_registry_reuses_identity_and_resolves_all_target_criteria():
    registry = DocumentRegistry()
    first = registry.reconcile((part_a, part_b))
    second = registry.reconcile((part_a, part_b))
    assert first[0].id == second[0].id
    assert registry.resolve(TargetBinding(path=part_a.path)) == first[0]
    assert registry.resolve(TargetBinding(title=part_a.title)) == first[0]
    assert registry.resolve(TargetBinding(document_type=DocumentType.PART)) is not None

def test_registry_drops_closed_documents_and_rejects_old_id():
    registry = DocumentRegistry()
    handle = registry.reconcile((part_a,))[0]
    registry.reconcile(())
    with pytest.raises(TargetNotFoundError):
        registry.resolve(TargetBinding(document_id=handle.id))
```

- [ ] **Step 2: Run registry tests to verify the expected missing-symbol failure**

Run: `uv run pytest tests/runtime/test_registry.py -q`

Expected: FAIL because `cadipy.runtime.DocumentRegistry` is not implemented.

- [ ] **Step 3: Write failing session ownership and adapter-sharing tests**

```python
def test_session_shares_one_dispatcher_with_rpc_and_mcp(fake_executor):
    with CadipySession(executor=fake_executor, connection_mode="attach") as session:
        assert session.server.dispatcher is session.dispatcher
        assert session.mcp.server.dispatcher is session.dispatcher
        session.execute("application.info")
    with pytest.raises(SessionClosedError):
        session.execute("application.info")
```

- [ ] **Step 4: Run session tests to verify the expected missing-symbol failure**

Run: `uv run pytest tests/runtime/test_session.py -q`

Expected: FAIL because the session module and lifecycle contract are not implemented.

- [ ] **Step 5: Commit the failing contract tests**

```powershell
git add tests/runtime
git commit -m "test: define persistent session contracts"
```

### Task 2: Implement domain values and the session-local document registry

**Files:**
- Create: `src/cadipy/runtime.py`
- Modify: `src/cadipy/domain/errors.py`
- Modify: `src/cadipy/backends/executor.py`

**Interfaces:**
- `DocumentRegistry.reconcile(handles: Iterable[DocumentHandle]) -> tuple[DocumentHandle, ...]` preserves IDs by `(path, document_type, title)` identity and removes absent documents.
- `DocumentRegistry.resolve(binding: TargetBinding) -> DocumentHandle` delegates deterministic matching to domain target rules and raises the existing target errors.
- `SessionClosedError` has code `session_closed`.
- `ApplicationInfo` adds `connection_mode: str` and `owned: bool` with backward-compatible defaults.

- [ ] **Step 1: Implement the minimal registry and error types**

Use a private identity map and a live handle map. The registry may replace a backend-discovered handle's opaque ID with the prior session ID, but it must never retain COM values or infer a target from active UI focus.

- [ ] **Step 2: Run the focused pure tests**

Run: `uv run pytest tests/runtime/test_registry.py -q`

Expected: PASS.

- [ ] **Step 3: Refactor only after the focused tests are green**

Keep matching in `cadipy.domain.targets`; the runtime registry owns lifecycle reconciliation, not a second matching algorithm.

- [ ] **Step 4: Commit the registry boundary**

```powershell
git add src/cadipy/runtime.py src/cadipy/domain/errors.py src/cadipy/backends/executor.py tests/runtime/test_registry.py
git commit -m "feat: add session document registry"
```

### Task 3: Implement explicit executor lifecycle and live SOLIDWORKS document discovery

**Files:**
- Modify: `src/cadipy/backends/solidworks/application.py`
- Modify: `src/cadipy/backends/solidworks/documents.py`
- Modify: `src/cadipy/backends/solidworks/executor.py`
- Modify: `tests/backends/test_executor_contract.py`

**Interfaces:**
- `SolidWorksExecutor.attach() -> ApplicationInfo`, `launch() -> ApplicationInfo`, `connect() -> ApplicationInfo`, `application_info() -> ApplicationInfo`, `list_documents() -> tuple[DocumentHandle, ...]`, `active_document() -> DocumentHandle | None`, and `open_document(path: Path, document_type: DocumentType = DocumentType.PART) -> DocumentHandle`.
- `PythonComSolidWorksExecutor.disconnect()` clears session-local handles and exits only an owned launched application.
- The backend uses `GetActiveObject` for attach, `DispatchEx` for launch, `GetDocuments` for enumeration, `ActiveDoc` for reporting, and `OpenDoc6` for opening Parts; unsupported document types fail through the domain error model.

- [ ] **Step 1: Extend fake worker and backend contract tests before production changes**

Assert both executor implementations expose the new serializable methods and that `ApplicationInfo` reports `connection_mode` and `owned` without a COM field.

- [ ] **Step 2: Run the focused contract tests to verify failure**

Run: `uv run pytest tests/backends/test_executor_contract.py -q`

Expected: FAIL because the fake worker and Python COM executor do not yet implement the new port.

- [ ] **Step 3: Implement attach/launch ownership and safe disconnect**

Keep COM acquisition and shutdown in the backend application wrapper. `attach` must not fall back to launch; `launch` must set ownership only after successful creation.

- [ ] **Step 4: Implement live document enumeration and opening**

Convert each live COM document immediately to a `DocumentHandle`, normalize saved paths, and update the private COM map. Use the existing document type conversion and centralized error mapping.

- [ ] **Step 5: Run focused backend tests and the existing import tests**

Run: `uv run pytest tests/backends -q`

Expected: PASS.

- [ ] **Step 6: Commit the executor port and COM lifecycle**

```powershell
git add src/cadipy/backends tests/backends
git commit -m "feat: add explicit application and document lifecycle"
```

### Task 4: Add authoritative P0 operation contracts and dispatcher handlers

**Files:**
- Modify: `src/cadipy/operations/registry.py`
- Modify: `src/cadipy/operations/dispatch.py`
- Modify: `tests/operations/test_dispatch.py`
- Modify: `tests/test_schema_consistency.py` if explicit operation groups are asserted.

**Interfaces:**
- Registry adds `application.attach`, `application.launch`, `application.info`, `document.list`, `document.active`, `document.open`, and `document.close`.
- Dispatcher invokes only executor semantic methods and passes the one resolved `DocumentHandle` to `document.close`/`document.inspect`/`part.rebuild`.
- Target parsing includes `document_type` as `DocumentType` and rejects unknown values with `InvalidArgumentError`.

- [ ] **Step 1: Write failing dispatch tests**

```python
def test_document_close_resolves_target_once(dispatcher, executor):
    result = dispatcher.dispatch({
        "id": "close-1",
        "operation": "document.close",
        "target": {"document_id": "doc-a"},
        "params": {},
    })
    assert result.ok
    assert executor.closed_ids == ["doc-a"]
```

- [ ] **Step 2: Run the focused test to verify failure**

Run: `uv run pytest tests/operations/test_dispatch.py -q`

Expected: FAIL because the operation is absent from the registry/dispatcher.

- [ ] **Step 3: Implement registry entries, target type parsing, and handlers**

`document.list` and `document.active` return serialized handle data; `document.open` validates a path and optional document type; `application.*` calls the corresponding lifecycle method; `document.close` requires the existing explicit target path.

- [ ] **Step 4: Run operation and schema tests**

Run: `uv run pytest tests/operations tests/test_schema_consistency.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the operation contracts**

```powershell
git add src/cadipy/operations tests/operations tests/test_schema_consistency.py
git commit -m "feat: expose session and document operations"
```

### Task 5: Implement the public session and preserve one-shot API compatibility

**Files:**
- Create: `src/cadipy/session.py`
- Modify: `src/cadipy/api.py`
- Modify: `src/cadipy/__init__.py`
- Modify: `src/cadipy/protocol/server.py`
- Modify: `src/cadipy/protocol/mcp.py` only if a typed session constructor is needed.
- Modify: `tests/runtime/test_session.py`
- Modify: `tests/protocol/test_adapters.py`

**Interfaces:**
- `CadipySession(executor: SolidWorksExecutor | None = None, connection_mode: Literal["attach", "launch"] = "attach", audit_recorder: AuditRecorder | None = None)`.
- `CadipySession.__enter__() -> CadipySession`, `__exit__`, `execute(operation, *, params=None, target=None, request_id="session-api")`, `create_part() -> DocumentHandle`, `list_documents()`, `active_document()`, `open(path, document_type=DocumentType.PART)`, `inspect(target)`, `rebuild(target)`, `close(target)`, and `server`/`mcp` adapter properties.
- `connect(mode="attach", *, executor=None) -> CadipySession`; `launch(*, executor=None) -> CadipySession`.
- `execute()` with an omitted executor uses a temporary attach session; a caller-supplied executor remains caller-owned.

- [ ] **Step 1: Run the existing failing session tests**

Run: `uv run pytest tests/runtime/test_session.py tests/protocol/test_adapters.py -q`

Expected: FAIL because no session owns the dispatcher/resolver yet.

- [ ] **Step 2: Implement session construction and context lifecycle**

Build one dispatcher with the registry resolver and audit recorder. On entry call `attach` or `launch`; after exit mark closed before disconnecting. Session convenience methods call `execute`, never backend methods directly.

- [ ] **Step 3: Make RPC and MCP use the session dispatcher**

Add `ProtocolServer.from_session(session)` and ensure its identity is the same dispatcher used by Python calls. Keep `from_executor` for compatibility as a one-shot adapter.

- [ ] **Step 4: Route the one-shot API through the session without changing its result contract**

Do not change existing operation names or serialized result fields. Preserve caller-owned executor behavior.

- [ ] **Step 5: Run focused session, protocol, and API tests**

Run: `uv run pytest tests/runtime tests/protocol tests/operations -q`

Expected: PASS.

- [ ] **Step 6: Commit the public runtime**

```powershell
git add src/cadipy/session.py src/cadipy/api.py src/cadipy/__init__.py src/cadipy/protocol tests/runtime tests/protocol
git commit -m "feat: add persistent CAD session API"
```

### Task 6: Add real SOLIDWORKS session and target-race verification

**Files:**
- Create: `tests/integration/solidworks/test_session_target_race.py`
- Modify: `tests/integration/solidworks/conftest.py`
- Modify: `docs/usage.md`, `docs/usage.en.md`, `docs/protocol.md`, `docs/protocol.en.md`, `docs/api/index.md`, `docs/api/index.en.md`

**Interfaces:**
- The integration fixture supplies a strict session connected to the supported SOLIDWORKS instance and tracks only documents created/opened by the test.
- The test uses `with cadipy.connect(mode="attach")`, creates Part A and Part B, binds A explicitly, changes active focus to B, then calls `part.rebuild` and `document.inspect` with A's `document_id`.

- [ ] **Step 1: Write the strict target-race test before fixture implementation**

```python
@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_explicit_target_survives_active_document_change(cad_session):
    part_a = cad_session.create_part()
    part_b = cad_session.create_part()
    cad_session.executor.activate_for_test(part_b)
    rebuilt = cad_session.rebuild(target=part_a)
    inspected = cad_session.inspect(target=part_a)
    assert rebuilt.data["success"] is True
    assert inspected.data["document_id"] == part_a.id
```

- [ ] **Step 2: Run the strict test to establish its initial failure**

Run: `$env:CADIPY_REQUIRE_REAL_SOLIDWORKS='1'; uv run pytest tests/integration/solidworks/test_session_target_race.py -vv; Remove-Item Env:CADIPY_REQUIRE_REAL_SOLIDWORKS`

Expected: FAIL until the session fixture and live resolver are implemented; an unavailable strict environment must fail, not skip.

- [ ] **Step 3: Implement test-owned document activation without adding a public COM API**

Use a test-only backend helper or activation through the test fixture. Do not add `activate_for_test` to the public executor port or public API.

- [ ] **Step 4: Run the strict target-race and existing round-trip contracts**

Run: `$env:CADIPY_REQUIRE_REAL_SOLIDWORKS='1'; uv run pytest -m real_solidworks -vv; Remove-Item Env:CADIPY_REQUIRE_REAL_SOLIDWORKS`

Expected: every strict test passes and reports actual target A inspection after focus changes; no test terminates an attached user application.

- [ ] **Step 5: Document session lifecycle and target identity**

Document attach vs launch, session-local IDs, explicit target criteria, close ownership, and shared RPC/MCP semantics in both language variants.

- [ ] **Step 6: Commit integration evidence and documentation**

```powershell
git add tests/integration/solidworks docs/usage.md docs/usage.en.md docs/protocol.md docs/protocol.en.md docs/api/index.md docs/api/index.en.md
git commit -m "test: verify live target resolution in a persistent session"
```

### Task 7: Run complete quality gates and review the branch

**Files:**
- Modify: none unless a gate exposes an issue.

- [ ] **Step 1: Run portable tests and coverage**

Run: `uv run pytest tests -q` and `uv run pytest -m "not solidworks" --cov=cadipy.domain --cov=cadipy.operations --cov=cadipy.protocol --cov=cadipy.verification --cov=cadipy.diagnostics --cov=cadipy.audit --cov-fail-under=85 -q`

Expected: all portable tests pass and the configured 85% line-coverage gate passes without broad COM exclusions.

- [ ] **Step 2: Run lint, format, and type checks**

Run: `uv run ruff check .; uv run ruff format --check .; uv run mypy src/cadipy`

Expected: all commands exit successfully.

- [ ] **Step 3: Run package and documentation checks**

Run: `uv build; uv run mkdocs build --strict; uv run python scripts/verify_package.py`

Expected: package build, strict documentation build, and wheel verification pass.

- [ ] **Step 4: Review the final diff and tracked files**

Run: `git diff main...HEAD --stat; git diff main...HEAD --check; git status --short`

Expected: only session/runtime work is present; no generated CAD files, private paths, secrets, or unrelated product history entered the branch.

- [ ] **Step 5: Commit any gate-only corrections separately and report exact evidence**

Use a focused `fix:` or `docs:` commit for any correction. Do not bump the package version for this stage.
