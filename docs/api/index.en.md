# Public API

`cadipy.execute()` accepts an operation name from the registry and ordinary Python values, then returns an `OperationResult` without COM objects.

The registry currently exposes application attach/launch/info, document list/active/open/close/create/inspect, rectangular extrusion, diagnostics, and Part rebuild operations. Parameter types, units, target requirements, and postconditions are all defined by `OPERATION_REGISTRY`; CLI, RPC, and MCP do not duplicate operation semantics.

## Persistent sessions

`cadipy.connect()` returns a `CadipySession` that attaches to an existing SOLIDWORKS instance on context entry. `cadipy.launch()` creates an explicitly owned application session. The session owns the executor, target resolver, dispatcher, and audit recorder. `create_part()`, `list_documents()`, `active_document()`, `open()`, `inspect()`, `rebuild()`, and `close()` all use the registry contract and expose no COM objects.
