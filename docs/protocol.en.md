# Protocol

Protocol version `1` carries an operation name, explicit parameters, an optional target, and a request id. Responses contain JSON-serializable domain values only. MCP and RPC submit through the session façade; they do not retain or call a dispatcher directly and never transmit live COM references. Each session processes requests FIFO on one dedicated STA execution thread, while the Python-facing request/response API remains synchronous.

Responses retain the existing fields and add a structured `execution` field in protocol version `1`:

```json
{
  "protocol": 1,
  "id": "request-1",
  "operation": "part.create_rectangular_extrude",
  "ok": true,
  "data": {"verification": "passed"},
  "error": null,
  "execution": {
    "phase": "committed",
    "state_certainty": "certain",
    "rollback_status": "not_attempted"
  }
}
```

Lifecycle phases are `received`, `validated`, `target_resolved`, `executed`, `rebuilt` when applicable, `verified`, `committed`, and the failure phases `verification_failed` and `failed`. A required postcondition failure returns `ok=false` with error code `verification_failed`; it must not be represented as `ok=true` with a failed verification field. A mutation-scope failure may report the `failed` phase after rollback while retaining the same error code.

`rollback_status` is one of `not_attempted`, `rolled_back`, `rollback_failed`, or `state_uncertain`. A timeout does not cancel an already-running COM call; it may have changed the model, and the host rejects queued work. The caller must clean up the session and reconnect before another mutation; automatic retry of an uncertain mutation is forbidden. The protocol makes no ACID, crash-safe, or exactly-once guarantee.

Persistent-session adapters still consume the same `OPERATION_REGISTRY` through the same session façade; the dispatcher remains host-confined. The current stage exposes `application.attach`, `application.launch`, `application.set_visibility`, `application.info`, `document.list`, `document.active`, `document.open`, and `document.close`. `application.launch` defaults to `visible=true`; `application.set_visibility` requires an explicit boolean, and `application.info` reports the current `visible` state. Targets may use `document_id`, `path`, `title`, `document_type`, and `configuration`. A `document_id` is valid only in the session that issued it; RPC and MCP never receive or return SOLIDWORKS COM objects.
