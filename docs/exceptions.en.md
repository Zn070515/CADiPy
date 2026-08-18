# Error semantics

Public failures inherit from `CadipyError` and expose stable codes, operation names, and machine-readable details. Backend HRESULTs, SOLIDWORKS return values, and raw exception chains remain diagnostic context rather than public contracts.

## Execution and mutation failures

- `verification_failed`: a required postcondition did not pass. The Python façade preserves the typed `VerificationError`; RPC, MCP, and CLI return `ok=false`. It can never be represented as `ok=true`.
- `worker`: the STA host, worker, disconnect, or timeout failed. A timeout does not cancel a running COM call; the call may still be running or may already have changed the model.
- `transaction`: a mutation is blocked by uncertain state, or one bounded rollback could not prove recovery.
- `execution.phase`: `received`, `validated`, `target_resolved`, `executed`, `rebuilt`, `verified`, `committed`, `verification_failed`, or `failed`.
- `execution.rollback_status`: `not_attempted`, `rolled_back`, `rollback_failed`, or `state_uncertain`. An uncertain state or unverifiable rollback requires closing and reconnecting the session before another mutation; automatic retry is forbidden.

Failure results may also include `state_certainty`. Do not interpret “the call returned” as “the model committed correctly”: success requires `ok=true` with `phase=committed`, while a required verification failure must be a failure result. The runtime provides bounded rollback only; it makes no ACID, crash-safe, or exactly-once guarantee.

Connection ownership is part of error handling. An existing SOLIDWORKS instance attached by `connect()` is not owned by CADiPy, so session cleanup releases references without terminating it. An instance created and owned by `launch()` may be closed by CADiPy. Rollback cleans up only resources explicitly created and owned by CADiPy.
