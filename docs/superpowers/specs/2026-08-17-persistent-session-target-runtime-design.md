# Persistent CAD Session & Live Target Resolution

## Status

Approved implementation scope for the current development stage.

## Goal

Make CADiPy capable of maintaining one explicit SOLIDWORKS execution session across multiple operations while resolving document targets from live SOLIDWORKS state. The public surface must remain backend-neutral and serializable; Python COM is an implementation detail behind `SolidWorksExecutor`.

## Scope

This stage includes:

- a context-managed `CadipySession` owning the executor, dispatcher, target resolver, and audit recorder;
- explicit attach and launch application modes;
- a session-local document registry reconciled with currently open SOLIDWORKS documents;
- document list, active, open, inspect, and close operations;
- target bindings by `document_id`, path, title, document type, and configuration;
- resolve-once dispatch semantics for every target-bound operation;
- serializable Python, RPC, and MCP access through the same dispatcher and registry;
- lifecycle and target-race tests, including a real SOLIDWORKS target-race contract when SOLIDWORKS is available.

This stage does not add new geometry families, sketch primitives, assembly operations, or a C# project. It preserves the existing rectangular extrusion contract and makes its executor reusable within a session.

## Non-goals

- public COM objects, COM object IDs, or backend-specific handles;
- a process-global active-document variable;
- implicit attachment followed by silent launch;
- termination of an application CADiPy did not launch;
- persistence of session-local `document_id` values across sessions;
- a second operation registry for any adapter.

## Public model

`CadipySession` is the primary Python workflow boundary:

```python
with cadipy.connect(mode="attach") as cad:
    part = cad.create_part()
    cad.rebuild(target=part)
    inspection = cad.inspect(target=part)
```

`cadipy.connect()` defaults to strict attach semantics. `cadipy.launch()` is an explicit convenience constructor for a new owned application instance. A session exposes `execute()` for arbitrary registered operations plus typed convenience methods that construct requests for the same dispatcher. `execute()` remains available as a one-shot compatibility API and creates a temporary attach session when no executor is supplied.

The session owns:

```text
COM apartment and executor
        ↓
DocumentRegistry / TargetResolver
        ↓
OperationDispatcher
        ↓
ProtocolServer and optional MCP adapter
```

The server and MCP adapter receive the session dispatcher; they do not resolve targets or invoke backend methods independently.

## Application lifecycle

The executor port gains semantic lifecycle methods:

- `attach()`: acquire an already-running registered SOLIDWORKS instance; fail with `SolidWorksNotAvailableError` if none is available;
- `launch()`: create a new SOLIDWORKS instance using the COM launch mechanism and mark it as owned by the executor;
- `connect()`: retained as a backwards-compatible alias for `attach()` for existing callers;
- `application_info()`: return serializable product, revision, executor, connection mode, and ownership information;
- `disconnect()`: release CADiPy references, invalidate session-local registries, and exit the COM apartment. Only an owned launch may be asked to exit, and attach must never terminate the existing instance.

The public `ApplicationInfo` value carries no live COM reference. A session is not reusable after context exit; calls after exit raise `SessionClosedError` before reaching the backend.

## Document registry and identity

The Python COM executor retains COM document references privately, keyed by opaque session-local IDs. `list_documents()` reconciles the registry from the current SOLIDWORKS `GetDocuments()` collection. `active_document()` reads `ActiveDoc` only to report the current active identity; it is never used as an implicit mutation target.

Each returned `DocumentHandle` contains only domain data:

- opaque `id` valid only during the session;
- `DocumentType`;
- title;
- normalized path when the document is saved;
- configuration when available.

When an existing open document is discovered, the registry reuses its handle if its stable identity matches a prior entry in the current session. When a document is closed or no longer appears in the live collection, its handle is removed from the resolvable registry. A saved document can be found in a later session through path/title/type criteria; its old session-local ID cannot be reused.

`document.open` accepts a path and optional document type, uses the corresponding official SOLIDWORKS open call, then registers the returned document. `document.close` resolves one registered document and closes only that document. Existing save/reopen behavior remains available to the contract fixture, with reopened documents receiving a new session-local identity.

## Target resolution

The dispatcher converts request target data into one `TargetBinding`, including `document_type`. The session resolver reconciles live documents, applies the existing deterministic matching rules, and returns exactly one `DocumentHandle`.

For each operation:

1. validate the `OpSpec` and request target;
2. resolve exactly once before backend invocation;
3. pass that resolved handle to every backend call in the operation;
4. never consult UI focus or re-resolve during the operation.

Mutating operations require an explicit target. Read-only document inspection may later opt into a documented active-document policy, but this stage keeps `document.inspect` explicit to avoid accidental ambiguity.

## Operation contracts

The authoritative registry adds:

```text
application.attach   read-only, no target
application.launch   mutating application lifecycle, no target
application.info     read-only, no target
document.list        read-only, no target
document.active      read-only, no target
document.open        mutating, no target, path + document_type
document.close       mutating, explicit target
```

The existing `diagnostics.connect`, `document.create_part`, `document.inspect`, `part.rebuild`, and rectangular extrusion operations remain registered and continue through the same dispatcher. Adapter operation lists are derived from `OPERATION_REGISTRY`; schema consistency tests must cover the additions.

## Error and lifecycle semantics

- attach with no registered application: `SolidWorksNotAvailableError`;
- use of a closed session: `SessionClosedError`;
- target ID not in the live session registry: `TargetNotFoundError`;
- criteria matching zero or multiple documents: existing `TargetMismatchError` or `AmbiguousSelectionError`;
- a document disappearing between registry reconciliation and backend use: `TargetNotFoundError` or a backend `ComOperationError` with the target identity, never silent fallback to the active document;
- close of an attached application: releases CADiPy references only;
- close of a launched application: may exit the owned application after owned documents are cleaned up according to the session policy.

All errors remain serializable through `OperationResult`; no COM exception or live COM value crosses the public/protocol boundary.

## Verification

Pure tests will prove:

- session context owns and releases its components;
- `CadipySession.execute`, RPC, and MCP share one dispatcher and resolver;
- attach, launch, and application info contracts are explicit;
- document registry matching supports all target criteria;
- session-local IDs expire after close and are not accepted after session exit;
- a target is resolved once and remains the argument to the backend even if the active document changes;
- registry and adapter operation lists remain identical.

Real SOLIDWORKS tests will prove:

1. attach to the existing instance without owning or quitting it;
2. create/open two test-owned Part documents;
3. bind Part A, activate/open Part B, then rebuild and inspect A by explicit target;
4. verify A changed and B did not become the operation target;
5. enumerate, inspect, close, and clean up only test-owned documents.

The existing 100×60×3 mm rectangular extrusion round-trip remains a long-term real-SOLIDWORKS fixture and will run through a session-owned executor where applicable.

## Compatibility and documentation

Existing `execute()` and `connect()` behavior remains available. New session APIs and explicit lifecycle semantics are documented in the Python API, usage, protocol, and migration documentation. No version bump is part of this stage.
