# Error semantics

Public failures inherit from `CadipyError` and expose stable codes, operation names, and machine-readable details. Backend HRESULTs, SOLIDWORKS return values, and raw exception chains remain diagnostic context rather than public contracts.

## Execution and mutation failures

- `verification_failed`: a required postcondition did not pass. Direct Python `CadipySession`/dispatcher callers receive the typed `VerificationError`; RPC and MCP return an `ok=false` envelope. The current CLI prints `OperationResult.to_dict()` on its success path and returns 0/1 from `result.ok`, but an operation exception escapes `main()` as a process-level error rather than a uniform JSON failure response; malformed `--params-json` is the special case that prints a minimal `ok=false` JSON response and returns 2. This failure can never be represented as `ok=true`.
- `worker`: the STA host, worker loop, disconnect, or timeout failed. An ordinary command exception, including a backend or COM exception raised by the command, is delivered to the caller while the host continues; a timeout does not cancel a running COM call, which may still be running or may already have changed the model.
- `transaction`: a mutation is blocked by uncertain state, or one bounded rollback could not prove recovery.
- `execution.phase`: `received`, `validated`, `target_resolved`, `executed`, `rebuilt`, `verified`, `committed`, `verification_failed`, or `failed`.
- `execution.rollback_status`: `not_attempted`, `rolled_back`, `rollback_failed`, or `state_uncertain`. An uncertain state or unverifiable rollback requires closing and reconnecting the session before another mutation; automatic retry is forbidden.

Failure results may also include `state_certainty`. Do not interpret “the call returned” as “the model committed correctly”: success requires `ok=true` with `phase=committed`, while a required verification failure must be a failure result in the protocol envelope. The runtime provides bounded rollback only; it makes no ACID, crash-safe, or exactly-once guarantee and does not promise automatic recovery from a SOLIDWORKS process crash.

Connection ownership is part of error handling. `connect()` starts an attach-mode session and `launch()` starts a new launch-mode session. Do not call `application.launch` through an already attached session: the current backend retains the existing application reference but changes its ownership flag, so disconnect may call `ExitApp` on the previously attached instance; the implementation does not currently reject this transition. End the attach session before creating a new `launch()` session. Rollback cleans up only resources explicitly created and owned by CADiPy.
