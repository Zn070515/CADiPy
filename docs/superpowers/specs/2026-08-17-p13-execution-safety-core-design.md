# P1.3-A Execution Safety Core Design

## Status

Accepted direction; implementation pending plan review.

This design covers the first P1.3 hardening stage only. It does not add a new
SOLIDWORKS modeling feature family, CLI command, MCP tool, or public COM escape
hatch.

## Goal

Establish a backend-neutral execution boundary in which every operation for a
session is serialized through one owned execution context, all Python COM calls
run on one dedicated STA thread, OpSpec declarations are enforced at runtime,
and required postconditions and multi-step mutation failures have explicit
result semantics.

The public contract remains composed of CADiPy domain values, operation results,
and stable domain errors. No live SOLIDWORKS COM object may cross the execution
boundary.

## Current baseline and problem statement

The current `CadipySession` owns an executor, dispatcher, target registry, RPC
server, and MCP adapter, but `session.execute()` calls the dispatcher directly
on its caller's thread. `PythonComSolidWorksExecutor` initializes an STA when
it first connects, so a future concurrent RPC or MCP caller could invoke COM
through the wrong thread. The current `OpSpec.parameters` values are mutable
dictionaries with basic type checks, and `document_types` and
`postconditions` are not yet complete runtime enforcement. The rectangular
extrusion path can return a successful result containing a failed verification
status, which makes `ok=True` unsafe for agents to consume.

## Design decisions

### 1. Dedicated execution host

Introduce a backend-neutral `ExecutorHost` protocol and an in-process
`StaExecutorHost` implementation. The host owns:

* one dedicated worker thread;
* a FIFO command queue;
* the executor and dispatcher state used by that session;
* startup and shutdown state;
* the only thread allowed to call executor methods.

Conceptual interface:

```python
class ExecutorHost(Protocol):
    def start(self, initialize: Callable[[], None]) -> None: ...
    def submit(self, command: Callable[[], T]) -> T: ...
    def close(self) -> None: ...
```

The concrete host may use `queue.Queue`, a worker `Thread`, and a completion
`Future` implemented with standard-library synchronization primitives. A
submitted command runs to completion before the next command begins. The
synchronous Python API waits for the command result, preserving its current
call style while making execution serialized.

For the Python COM backend, host startup constructs or activates the executor
on the worker thread and initializes its COM apartment there. Attach/launch,
all executor calls, and disconnect run on that same thread. The COM apartment
must remain initialized for the lifetime of the worker and be uninitialized
only after disconnect has completed. The host must never return an executor,
COM reference, or backend-owned registry to a caller.

`CadipySession.__enter__`, `execute`, and `__exit__` become host operations:

```text
enter  -> start STA host -> attach or launch on host
execute -> enqueue dispatcher.dispatch -> return serializable result
exit   -> enqueue disconnect -> stop and join host
```

If a command is submitted from the host thread itself, the host may execute it
directly to avoid self-deadlock. This is an internal re-entrancy rule only; it
does not permit public callers to obtain COM objects.

Host lifecycle states are `created`, `running`, `closing`, `closed`, and
`failed`. A failed or closed host rejects new commands with a stable
`SessionClosedError` or `WorkerError`; it never silently starts a second
executor. Shutdown joins the worker and reports a failure if the worker cannot
terminate within the configured bounded timeout.

The host is deliberately expressed in terms of an executor port rather than
Python COM details. A future C# worker host can satisfy the same semantic
submission contract without changing Python-facing operations or results.

### 2. Immutable typed operation schema

Replace untyped parameter declaration dictionaries with immutable standard
library values. The schema remains small and dependency-free:

```python
class ParamType(str, Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    PATH = "path"
    OBJECT = "object"
    ARRAY = "array"

@dataclass(frozen=True, slots=True)
class ParamSpec:
    type: ParamType
    required: bool = False
    default: Any = _MISSING
    unit: str | None = None
    finite: bool = False
    minimum: float | None = None
    exclusive_minimum: float | None = None
    maximum: float | None = None
    exclusive_maximum: float | None = None
    choices: frozenset[str] | None = None

@dataclass(frozen=True, slots=True)
class PostconditionSpec:
    name: str
    required: bool = True

@dataclass(frozen=True, slots=True)
class OpSpec:
    ...
    parameters: Mapping[str, ParamSpec]
    target_document_types: frozenset[DocumentType] = frozenset()
    result_document_types: frozenset[DocumentType] = frozenset()
    postconditions: tuple[PostconditionSpec, ...] = ()
```

The schema validates unknown parameters, required/default values, exact
primitive types, finite numeric values, numeric bounds, choices, and public
unit declarations at the dispatcher boundary. `bool` is never accepted as a
number or integer. `NaN`, positive infinity, and negative infinity are
rejected before a backend call. Public dimensions continue to use CADiPy
engineering units such as millimetres; conversion to SOLIDWORKS internal units
remains a backend concern.

The schema is authoritative for registry serialization, CLI/RPC/MCP exposure,
and runtime validation. No adapter may reconstruct a second parameter schema.

After a target is resolved, the dispatcher checks the resolved
`DocumentHandle.document_type` against `OpSpec.target_document_types`. An
operation whose target document type is not allowed fails with a stable
`DocumentTypeError` before invoking the executor. Targetless document
operations declare `result_document_types` for the document type they create
or open; the dispatcher also validates the requested `document_type` choice
against that declaration. Application-level operations leave both sets empty.

### 3. Executable postconditions and result states

Postconditions become typed declarations with a verifier selected by the
shared verification layer. A postcondition has an identifier, whether it is
required, and the data needed by its verifier; it does not contain COM
objects.

Each dispatch records an internal lifecycle:

```text
RECEIVED
  -> VALIDATED
  -> TARGET_RESOLVED
  -> EXECUTED
  -> REBUILT              (when applicable)
  -> VERIFIED             (all required checks pass)
  -> COMMITTED
```

Failure transitions are explicit:

```text
validation_failed
target_failed
execution_failed
rebuild_failed
verification_failed
rollback_attempted
rolled_back | rollback_failed | state_uncertain
```

An operation with a required postcondition can never produce a successful
`OperationResult`. A verification failure raises/serializes
`VerificationError` with the stable code `verification_failed`, and protocol
adapters return `ok: false`. The old shape in which `ok: true` contains
`verification: "failed"` is removed. Optional observations may remain in
successful data, but a failed required check is an operation failure.

Direct Python calls retain typed CADiPy error propagation where that is the
existing API convention; RPC, MCP, and CLI serialization all use the same
failure result contract. Tests must assert both paths.

### 4. Mutation scope and bounded rollback

Introduce an internal `MutationScope` around composite mutating operations. It
captures the resolved target identity and operation state, starts a backend
undo recording when the executor capability supports it, and owns the
commit/rollback decision.

The scope interface is semantic:

```python
with mutation_scope(executor, target, operation) as mutation:
    mutation.step("create sketch", action)
    mutation.step("create geometry", action)
    mutation.step("create feature", action)
    mutation.rebuild()
    mutation.verify(required_postconditions)
```

On successful verification, the scope finishes the undo recording and enters
`committed`. On a failure it attempts one rollback, verifies the rollback when
the backend can provide a reliable observation, and reports one of:

* `rolled_back`: the pre-mutation observable state was restored;
* `rollback_failed`: rollback was attempted but did not complete;
* `state_uncertain`: the call or rollback result cannot prove the model state.

This is not advertised as ACID or crash-safe transactionality. A COM process
failure, timeout, or ambiguous undo result must stop subsequent mutation in the
session until the session is closed/reconnected. Automatic retry of a mutation
with uncertain state is forbidden.

The initial implementation applies the scope to the existing rectangular
extrusion composite and provides a backend capability seam for SOLIDWORKS undo
recording. It does not claim that every individual future operation is already
transactional.

## Public compatibility and non-goals

* `cadipy.connect()` and `cadipy.launch()` remain the public session factories.
* Public handles and reports remain serializable dataclasses; no COM object is
  added to any result.
* The Python COM executor remains the current backend; no C# project is added
  in this stage.
* No new modeling operation family is added.
* Save/close file policy, protocol redaction, idempotency, audit sink design,
  entity-path consolidation, handler decomposition, and capability matrices
  remain subsequent P1.3 stages. This stage only exposes the seams needed by
  those stages.
* The existing 100×60×3 mm real-SOLIDWORKS round-trip fixture remains a
  required regression contract and must execute through the STA host.

## Testing and acceptance evidence

### Pure Python tests

Add tests for:

* FIFO ordering and single-thread execution of the host;
* host startup, close, failure, timeout, and rejection after close;
* executor lifecycle methods executing on the host thread;
* concurrent callers receiving their own results without COM calls leaving the
  host thread;
* typed parameter validation for missing values, unknown values, booleans,
  non-finite numbers, bounds, units, and choices;
* resolved document type enforcement;
* required postcondition failure producing a failure result and never `ok=True`;
* mutation state transitions and rollback outcomes with a fake semantic
  executor;
* session helpers continuing to return domain handles after host dispatch.

### Real SOLIDWORKS tests

The strict self-hosted suite must continue to run with
`CADIPY_REQUIRE_REAL_SOLIDWORKS=1` and must verify:

* launch/attach and disconnect occur on the host thread;
* concurrent requests are serialized while operating on the requested target;
* the 100×60×3 mm round-trip contract passes through the host;
* a deliberately failed verification is reported as an operation failure;
* an owned launched instance is cleaned up, while a user-owned instance is not
  terminated by CADiPy.

The normal portable suite may use fake executors for host and state-machine
tests. It must not use mocks to claim the real-SOLIDWORKS contract passed.

## Acceptance criteria

P1.3-A is complete only when:

1. All SOLIDWORKS executor lifecycle and operation calls from a session execute
   on one dedicated STA thread.
2. The same OpSpec values drive serialization and runtime validation.
3. Wrong target document types, non-finite values, and invalid numeric bounds
   fail before backend mutation.
4. A required verification failure is never represented as `ok=True`.
5. The rectangular composite has explicit commit, rollback, and uncertain-state
   behavior with tests for each outcome.
6. The strict real-SOLIDWORKS contract passes through the host, and the
   portable quality/coverage gates remain green.
7. Documentation states the concurrency, result, and rollback guarantees
   without claiming ACID or exactly-once semantics.
