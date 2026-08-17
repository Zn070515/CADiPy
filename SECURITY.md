# CADiPy Security Model

CADiPy can drive the local SOLIDWORKS process and therefore has the same authority as the user over documents opened in that session. Keep RPC transports on loopback or an explicitly protected private channel, authenticate remote callers before dispatch, and never expose live COM objects.

Operation requests must use the shared schema, require explicit targets for mutating existing-document operations, and reject ambiguous selections. Errors crossing protocol boundaries use stable codes and omit raw tracebacks, private paths, secrets, and COM representations.

Report security issues privately with a reproduction, affected operation, environment, and impact assessment. Do not attach confidential CAD files unless necessary.
