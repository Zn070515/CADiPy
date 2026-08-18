# Error semantics

Public failures inherit from `CadipyError` and expose stable codes, operation names, and machine-readable details. Backend HRESULTs, SOLIDWORKS return values, and raw exception chains remain diagnostic context rather than public contracts.

## Execution and mutation failures

- `verification_failed`: a required postcondition did not pass. Direct Python `CadipySession`/dispatcher callers receive the typed `VerificationError`; RPC and MCP return an `ok=false` envelope. The current CLI prints `OperationResult.to_dict()` on its success path and returns 0/1 from `result.ok`, but an operation exception escapes `main()` as a process-level error rather than a uniform JSON failure response; malformed `--params-json` is the special case that prints a minimal `ok=false` JSON response and returns 2. This failure can never be represented as `ok=true`.
- `worker`: the STA host, worker loop, or disconnect failed. An ordinary command exception, including a backend or COM exception raised by the command, is delivered to the caller while the host continues. On timeout, the caller receives and re-raises the built-in `TimeoutError`; the host enters `failed`, and later submissions receive `WorkerError`. A timeout does not cancel a running COM call, which may still be running or may already have changed the model.
- `transaction`: a mutation is blocked by uncertain state, or one bounded rollback could not prove recovery.
- `execution.phase`: `received`, `validated`, `target_resolved`, `executed`, `rebuilt`, `verified`, `committed`, `verification_failed`, or `failed`.
- `execution.rollback_status`: `not_attempted`, `rolled_back`, `rollback_failed`, or `state_uncertain`. An uncertain state or unverifiable rollback requires closing and reconnecting the session before another mutation; automatic retry is forbidden.

Failure results may also include `state_certainty`. Do not interpret “the call returned” as “the model committed correctly”: success requires `ok=true` with `phase=committed`, while a required verification failure must be a failure result in the protocol envelope. The runtime provides bounded rollback only; it makes no ACID, crash-safe, or exactly-once guarantee and does not promise automatic recovery from a SOLIDWORKS process crash.

Connection ownership is part of error handling. `connect()` starts an attach-mode session and `launch()` starts a new launch-mode session. Acquisition in the same mode is idempotent; a conflicting attach/launch acquisition raises the stable `ApplicationOwnershipError` and cannot reclassify the existing application. Disconnect exits an application only when CADiPy owns a launch-mode instance. Rollback cleans up only resources explicitly created and owned by CADiPy.

File persistence is guarded separately. `document.save` and composite `save_path` use `overwrite=False` by default; a pre-existing destination raises `FileConflictError` before `SaveAs2` and remains untouched. `overwrite=True` explicitly permits replacement. If a later operation fails after such an overwrite, rollback is reported uncertain unless a backup exists.
