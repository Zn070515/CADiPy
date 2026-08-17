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
    def start(self) -> None: ...
    def submit(self, command: Callable[[], T], *, timeout: float | None = None) -> T: ...
    def close(self, *, timeout: float) -> None: ...
```

The concrete host may use `queue.Queue`, a worker `Thread`, and a completion
`Future` implemented with standard-library synchronization primitives. A
submitted command runs to completion before the next command begins. The
synchronous Python API waits for the command result, preserving its current
call style while making execution serialized.

For the Python COM backend, production session construction stores an executor
factory; the factory constructs the executor on the worker thread after the
STA has started. Test sessions may provide a preconstructed semantic fake, but
it must not acquire COM before the host starts. Attach/launch, all executor
calls, and disconnect run on the same worker thread. The COM apartment must
remain initialized for the lifetime of the worker and be uninitialized only
after disconnect has completed. The host must never return an executor, COM
reference, or backend-owned registry to a caller.

The host also owns the mutable execution state: `DocumentRegistry`, the
dispatcher instance, and the audit recorder used by that dispatcher are
created or bound during host startup and accessed only by host commands. The
RPC and MCP adapters submit through the session/host façade; they do not retain
a dispatcher reference that can be called directly from a transport thread.
Any compatibility attribute exposing an executor must be a semantic proxy and
must not expose the live backend instance.

`CadipySession.__enter__`, `execute`, and `__exit__` become host operations:

```text
enter  -> start STA host -> attach or launch on host
execute -> enqueue dispatcher.dispatch -> return serializable result
exit   -> enqueue disconnect -> stop and join host
```

Normal close transitions the host to `closing`, rejects new submissions,
places a sentinel after already accepted commands, runs disconnect before the
sentinel, and joins the worker. If the host is already `failed`, pending
commands are rejected and the host attempts disconnect once on the worker
before joining. `CadipySession.__exit__` performs this sequence in `finally`,
so a dispatcher or disconnect exception cannot skip host shutdown. A
Python-COM executor exits SOLIDWORKS only when its ownership flag is true;
disconnecting from a user-owned application releases CADiPy's references but
does not close or terminate that application.

If a command is submitted from the host thread itself, the host may execute it
directly to avoid self-deadlock. This is an internal re-entrancy rule only; it
does not permit public callers to obtain COM objects.

Host lifecycle states are `created`, `running`, `closing`, `closed`, and
`failed`. A failed or closed host rejects new commands with a stable
`SessionClosedError` or `WorkerError`; it never silently starts a second
executor. Shutdown joins the worker and reports a failure if the worker cannot
terminate within the configured bounded timeout; the initial default for host
shutdown is 30 seconds. A command timeout does not
kill a Python thread or a COM call. Instead, the caller receives `WorkerError`,
the host enters `failed`, queued commands are rejected, and the host attempts
an orderly shutdown. The session must be closed/reconnected before any further
mutation. This prevents a caller from assuming that a timed-out command did
not mutate the model.

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
    verifier: str | None = None

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

The verification layer owns a registry from `PostconditionSpec.verifier` (or
the postcondition name when omitted) to a pure verifier callable. The callable
receives serialized operation data and semantic inspection values; it never
receives a COM object. An unknown verifier is a contract/configuration error
before the operation is allowed to report success.

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

The lifecycle is represented by a serializable `ExecutionReport` attached to
the operation result or its failure payload:

```python
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

@dataclass(frozen=True, slots=True)
class ExecutionReport:
    phase: ExecutionPhase
    state_certainty: Literal["certain", "uncertain"]
    rollback_status: Literal["not_required", "not_attempted", "rolled_back",
                             "rollback_failed"]
```

Successful operations end with `phase="committed"` and
`state_certainty="certain"`. Verification, rebuild, or execution failures
carry the last completed phase and rollback status. A timeout or ambiguous
rollback carries `state_certainty="uncertain"`; adapters must not reduce this
to a generic successful result. The existing serialized result keys remain
compatible, with the execution report added as a structured field rather than
encoded in a free-form message.

The additive execution field is included in the existing protocol version 1
schema and is covered by the existing schema-consistency tests. Existing
consumers that ignore unknown response fields remain valid; adapters must not
create a second result shape. A future incompatible result change requires a
new protocol version rather than silently changing version 1 semantics.

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

Before the first mutation, the scope captures a semantic `MutationSnapshot`:

* for an existing target, the stable document identity, dirty/save state, and
  the backend's available observable model fingerprint;
* for a target created inside the scope, an explicit `created_resource` marker
  and the owned document handle to close if rollback is required.

The initial rectangular composite uses the second form because it creates its
Part inside the operation. Subsequent P1.3 mutation handlers use the first form
only when the backend can prove a useful pre-mutation inspection. A snapshot is an
observation boundary, not a promise that SOLIDWORKS has database-style undo.

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

The backend capability seam exposes semantic actions such as
`begin_mutation`, `commit_mutation`, `rollback_mutation`, and
`verify_rollback`. The Python COM implementation may map these actions to
SOLIDWORKS undo recording or owned-document cleanup, but those COM method
names do not appear in the domain or protocol contract.

This is not advertised as ACID or crash-safe transactionality. A COM process
failure, timeout, or ambiguous undo result must stop subsequent mutation in the
session until the session is closed/reconnected. Automatic retry of a mutation
with uncertain state is forbidden.

There is no mid-command cancellation contract in this stage. A caller may
stop waiting for a result, but the host cannot safely interrupt a running COM
call; it must treat that command as potentially mutating, transition to
`failed`/`state_uncertain`, and reject subsequent mutation until cleanup and
reconnection.

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
* Python 3.10–3.13 portable compatibility remains required; the host and
  schema use only the standard library in this stage.

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
* an owned launched instance is cleaned up, while an attached user-owned
  instance created inside the isolated test fixture remains running after
  CADiPy disconnects.

The workflow preflight still rejects an instance that predates the job, so the
user-owned lifecycle test must create its unowned/attached application after
preflight and clean it up in its own test fixture. It must not weaken the
preflight or kill arbitrary pre-existing SOLIDWORKS processes.

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
