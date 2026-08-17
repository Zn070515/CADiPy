# P1 Implementation Plan: Persistent Sketch Entity Runtime and Parametric Sketch Core

## Constraints

- Work directly on `feat/parametric-sketch-core` in the repository root; no worktree.
- Preserve the P0 session/target baseline and existing rectangular extrusion contract.
- Use TDD: add a focused failing test before each production behavior.
- Keep `SolidWorksExecutor` semantic and C#-replaceable; no COM object crosses the port.
- Keep all operation definitions in the authoritative OpSpec registry.
- Use `uv`, Python 3.12, and the strict real-SOLIDWORKS gate when validating COM behavior.

## Phase 1: domain values and error contract

1. Add `SketchEntityType`, `RelationType`, and `DimensionType` enums in a CAD domain module.
2. Add immutable serializable values for `SketchEntityHandle`, `RelationHandle`, `DimensionHandle`, `SketchInspection`, `SketchEntityInspection`, and `DimensionInspection`.
3. Extend `SketchHandle` additively with an optional persistent reference while retaining existing positional construction.
4. Add `EntityReferenceInvalidError` with stable code `entity_reference_invalid` and diagnostics fields that do not leak raw COM objects or private paths.
5. Add pure tests for JSON-safe conversion, public-unit fields, enum validation, and invalid-reference error serialization.

## Phase 2: persistent-reference utility

1. Add a backend utility that converts COM-returned byte-like values to base64 and back to a SafeArray only inside the Python COM adapter.
2. Add a resolver that calls `GetObjectByPersistReference3(persist_id, byref_error_code)` and rejects null objects or non-success error codes.
3. Add narrow backend tests for memoryview/bytes normalization, SafeArray construction, successful resolution, null resolution, and error-code resolution.
4. Ensure no resolver path enumerates or selects a substitute entity.

## Phase 3: semantic executor port

1. Extend `SolidWorksExecutor` with semantic sketch methods for list/inspect, line/rectangle/circle/arc creation, relation/dimension creation and update, entity/dimension inspection, and persistent resolve.
2. Update the existing fake worker contract tests so a future C# worker must implement the same serializable signatures.
3. Preserve the old rectangle-specific methods used by `part.create_rectangular_extrude`; adapt them internally where safe without changing their public result.

## Phase 4: OpSpec and dispatcher

1. Add all P1 operation specs to `operations/registry.py`, including target type, mutability, parameters, result contract, unit fields, and expected errors.
2. Add dispatcher handlers that validate all references before calling the executor and pass semantic values only.
3. Add session convenience methods for the P1 operations; keep `execute()` as the common path consumed by RPC and MCP.
4. Add schema consistency tests proving registry names and parameter contracts are shared by Python, RPC, and MCP adapters.
5. Add fake-executor dispatch tests for every operation and for invalid entity/dimension references.

## Phase 5: Python COM implementation

1. Add internal geometry functions using verified `ISketchManager` APIs and centralized mm-to-metre conversion.
2. Create one persistent-reference-bearing handle per returned sketch entity and keep COM objects private in executor registries only for the active session.
3. Implement line, circle, arc, and four-independent-line rectangle creation without relying on current UI focus.
4. Implement relation selection and invocation using resolved entities, then inspect the resulting sketch relation state.
5. Implement dimension creation and update using resolved entities/parameters; convert values at the boundary and expose mm only.
6. Implement entity/dimension inspection from actual SOLIDWORKS state.
7. Handle rebuild and reopen by invalidating stale private COM caches and resolving from persisted references against the explicit reopened document target.

## Phase 6: pure and boundary verification

1. Add tests for target/reference ownership, resolve-once behavior, session-local ID invalidation, and no fallback on missing references.
2. Add tests for line/circle/arc geometry value mapping and dimension conversion.
3. Add tests for temporary selection clearing and error mapping around backend calls.
4. Run the portable 85% coverage gate and adjust structure rather than excluding normal logic.

## Phase 7: strict real-SOLIDWORKS golden fixture

1. Add a `real_solidworks` test that builds the parameterized 100 x 60 mm rectangle from four line operations.
2. Add and verify relations and dimensions from actual model state.
3. Rebuild, extrude 3 mm, save a temporary SLDPRT, close, reopen, and resolve all persisted handles.
4. Set 100 mm to 120 mm, rebuild, and assert the actual bounding box is approximately 120 x 60 x 3 mm.
5. Make strict mode fail on unavailable COM, unsupported capability, failed creation, failed resolve, failed verification, or failed cleanup; allow skips only in ordinary non-SW environments.
6. Run the existing rectangle and target-race contracts to ensure P0 remains green.

## Phase 8: documentation and final gates

1. Add public documentation for sketch operations, identity lifecycle, units, relation/dimension semantics, and strict integration evidence.
2. Review all new docs for private paths, machine data, secrets, and uncurated reasoning.
3. Run ruff format/check, mypy, portable tests/coverage, package build/smoke, MkDocs strict build, and strict real-SW tests.
4. Review `git diff --check`, `git status`, and the final diff for accidental generated CAD artifacts.
5. Commit the completed P1 work on the feature branch. Integration to `main` and push remain separate user-directed actions.

