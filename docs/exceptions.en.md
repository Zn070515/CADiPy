# Error semantics

Public failures inherit from `CadipyError` and expose stable codes, operation names, and machine-readable details. Backend HRESULTs, SOLIDWORKS return values, and raw exception chains remain diagnostic context rather than public contracts.
