# Public API

`cadipy.execute()` accepts an operation name from the registry and ordinary Python values, then returns an `OperationResult` without COM objects.

The registry currently exposes diagnostics, Part creation, document inspection, rectangular extrusion, and Part rebuild operations. Parameter types, units, target requirements, and postconditions are all defined by `OPERATION_REGISTRY`; CLI, RPC, and MCP do not duplicate operation semantics.
