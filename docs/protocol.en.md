# Protocol

Protocol version `1` carries an operation name, explicit parameters, an optional target, and a request id. Responses contain JSON-serializable domain values only. MCP and RPC are adapters over the same dispatcher and never transmit live COM references.

Persistent-session adapters still consume the same `OPERATION_REGISTRY` and session-owned dispatcher. The current stage adds `application.attach`, `application.launch`, `application.info`, `document.list`, `document.active`, `document.open`, and `document.close`. Targets may use `document_id`, `path`, `title`, `document_type`, and `configuration`. A `document_id` is valid only in the session that issued it; RPC and MCP never receive or return SOLIDWORKS COM objects.
