# Usage

Public lengths use `_mm` fields and angles use `_deg` fields. A rectangular extrusion uses `width_mm`, `height_mm`, and `depth_mm`; SOLIDWORKS meters and radians never cross the public boundary.

```python
from cadipy import execute

result = execute(
    "part.create_rectangular_extrude",
    params={"width_mm": 100.0, "height_mm": 60.0, "depth_mm": 3.0},
)
```

Results distinguish API calls, rebuild, verification, and save/reopen evidence. Use `cadipy check`, `cadipy server status`, or `cadipy operation <name> --params-json '<json>'` from the CLI.

## Execution safety contract

Each `CadipySession` owns one dedicated STA execution thread. The executor, dispatcher, target registry, connection/disconnection lifecycle, and Python COM calls run on that thread. Public APIs return serializable domain values only; live COM objects never cross the boundary. `execute()` is a synchronous façade: the caller waits for the result, and concurrent callers are serialized through the session queue instead of entering SOLIDWORKS concurrently.

The current 100×60×3 mm contract is:

```python
from cadipy import launch
from cadipy.domain.errors import CadipyError

with launch(visible=False) as cad:
    try:
        result = cad.execute(
            "part.create_rectangular_extrude",
            params={
                "plane": "Front Plane",
                "width_mm": 100.0,
                "height_mm": 60.0,
                "depth_mm": 3.0,
            },
        )
    except CadipyError as exc:
        raise RuntimeError(str(exc)) from exc
    assert result.ok
```

The `execution` report records the lifecycle. A successful operation normally passes through `received`, `validated`, `target_resolved`, `executed`, `rebuilt` when applicable, `verified`, and finally `committed`. A successful `OperationResult` has `ok=true` and may report `state_certainty` and `rollback_status`. A required postcondition failure always uses the stable `verification_failed` error code; the old shape of `ok=true` with `verification="failed"` is not success. Direct `CadipySession.execute()` and dispatcher callers receive typed `CadipyError` exceptions; RPC and MCP adapters serialize those failures as `ok=false` envelopes. A verification failure inside a mutation scope may have the terminal `failed` phase after rollback, but it can never be a successful result.

An ordinary command exception, including a backend or COM exception raised by the command, is delivered to the Python caller while the host continues and can accept later commands. That differs from a worker or process-level failure. On timeout, the caller receives and re-raises the built-in `TimeoutError`; the host simultaneously enters `failed`, queued calls are rejected, and later submissions receive `WorkerError`. A timeout does not cancel a running Python or COM call; the running call may already have changed the model. After a timeout or ambiguous result, close the session and reconnect before any further mutation. CADiPy never automatically retries an uncertain mutation and does not promise automatic recovery from a SOLIDWORKS process crash.

Mutation scopes make one bounded rollback attempt. `rollback_status` is one of `not_attempted`, `rolled_back`, `rollback_failed`, or `state_uncertain`. `rolled_back` is reported only when rollback is observably verified; a failed or unverifiable rollback requires session cleanup and reconnection before another mutation. This is not an ACID or crash-safe transaction and provides no exactly-once guarantee.

`connect()` starts in attach mode, while `launch()` starts a new session in launch mode. The executor records this ownership state: repeated acquisition in the same mode is idempotent, while an attach/launch mode conflict raises `application_ownership_conflict`. Disconnect calls `ExitApp` only for an application acquired through the owned launch mode. Rollback cleanup closes only documents or resources explicitly created and owned by CADiPy.

Use a persistent session when several operations belong to one SOLIDWORKS workflow. `connect()` strictly attaches to an already-running instance and preserves its current window visibility by default; use explicit `launch()` when CADiPy should create and own a new instance. `launch()` shows the new window by default, while automation can request `launch(visible=False)`. Session-local `document_id` values expire at session exit. Rebind a saved document in a later session by path, title, document type, or configuration.

```python
from cadipy import connect

with connect() as cad:
    part = cad.create_part()
    cad.rebuild(target=part)
    inspection = cad.inspect(target=part)
```

Application visibility is an application-level contract; it does not change document or model-entity visibility:

```python
from cadipy import launch

with launch(visible=True) as cad:
    part = cad.create_part()
    cad.set_visibility(False)
    cad.set_visibility(True)
```

`application.info` reports the current `visible` state, and protocol clients can call `application.set_visibility`. Public APIs never return SOLIDWORKS COM objects.

Document persistence is explicit. `document.save` and `part.create_rectangular_extrude(save_path=...)` use `overwrite=False` by default and raise `file_conflict` before replacing an existing destination; pass `overwrite=True` only when replacement is intentional. Closing a document defaults to `require_clean`: a dirty document must be closed with `save=True` or `discard=True`, and rollback uses an explicit discard for CADiPy-owned temporary documents. A newly created exact save path is removed during a verified rollback; an overwritten existing path cannot claim certain rollback without a backup.

Document targets must explicitly provide at least one of `document_id`, `path`, `title`, `document_type`, or `configuration`. Each operation resolves its target once before backend execution, so changing the SOLIDWORKS active document cannot redirect an explicitly bound operation. `document.list`, `document.active`, `document.open`, and `document.close` use the same session registry.

Parametric sketches are composed through the same session `execute()` method: `sketch.create` creates a plane sketch; `sketch.add_line`, `sketch.add_rectangle`, `sketch.add_circle`, and `sketch.add_arc` return serializable entity handles; `sketch.add_relation`, `sketch.add_dimension`, and `sketch.set_dimension` then modify the model. Public lengths remain millimetres, and saved/reopened entities are resolved through persistent references.
