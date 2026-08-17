# Public API

`cadipy.execute()` accepts an operation name from the registry and ordinary Python values, then returns an `OperationResult` without COM objects.

The registry currently exposes application attach/launch/set-visibility/info, document list/active/open/close/create/inspect, rectangular extrusion, Part rebuild, and composable parametric sketch operations (`sketch.create`, primitive creation, relations, dimensions, and inspection). Parameter types, units, target requirements, and postconditions are all defined by `OPERATION_REGISTRY`; CLI, RPC, and MCP do not duplicate operation semantics.

## Persistent sessions

`cadipy.connect()` returns a `CadipySession` that attaches to an existing SOLIDWORKS instance on context entry and preserves its current visibility by default. `cadipy.launch()` creates an explicitly owned application session and shows it by default; pass `visible=False` for automation. The session owns the executor, target resolver, dispatcher, and audit recorder. `create_part()`, `list_documents()`, `active_document()`, `open()`, `inspect()`, `rebuild()`, `close()`, and `set_visibility()` all use the registry contract and expose no COM objects. `application.info` reports the current `visible` state.

Sketch operations use serializable `SketchHandle`, `SketchEntityHandle`, `RelationHandle`, and `DimensionHandle` values. Entities are resolved through SOLIDWORKS persistent references across rebuild and save/reopen and are checked against the requested sketch's current segments. Dimensions retain sketch-scoped SOLIDWORKS parameter names while public values remain in millimetres. An invalid reference fails with the stable `entity_reference_invalid` error; CADiPy never substitutes an entity by order or current UI selection.
