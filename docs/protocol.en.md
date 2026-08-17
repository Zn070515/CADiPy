# Protocol

Protocol version `1` carries an operation name, explicit parameters, an optional target, and a request id. Responses contain JSON-serializable domain values only. MCP and RPC are adapters over the same dispatcher and never transmit live COM references.
