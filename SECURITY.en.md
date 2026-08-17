# CADiPy Security Model

CADiPy can drive the local SOLIDWORKS process and therefore has the user’s authority over documents in that session. Keep RPC transports on loopback or an explicitly protected private channel, authenticate callers, and never expose live COM objects.

Requests use the shared operation schema, mutating existing-document operations require explicit targets, and ambiguous selections fail. Protocol errors use stable codes without raw tracebacks, private paths, secrets, or COM representations.
