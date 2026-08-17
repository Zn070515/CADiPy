# Usage

Public lengths use `_mm` fields and angles use `_deg` fields. A rectangular extrusion uses `width_mm`, `height_mm`, and `depth_mm`; SOLIDWORKS meters and radians never cross the public boundary.

```python
from cadipy import execute

result = execute(
    "part.create_rectangular_extrude",
    params={"width_mm": 100.0, "height_mm": 60.0, "depth_mm": 3.0},
)
```

Results distinguish API calls, rebuild, verification, and save/reopen evidence. Use `cadipy check`, `cadipy server status`, or `cadipy operation <name> --params-json '<json>'` from the CLI.

Use a persistent session when several operations belong to one SOLIDWORKS workflow. `connect()` strictly attaches to an already-running instance; use explicit `launch()` when CADiPy should create and own a new instance. Session-local `document_id` values expire at session exit. Rebind a saved document in a later session by path, title, document type, or configuration.

```python
from cadipy import connect

with connect() as cad:
    part = cad.create_part()
    cad.rebuild(target=part)
    inspection = cad.inspect(target=part)
```

Document targets must explicitly provide at least one of `document_id`, `path`, `title`, `document_type`, or `configuration`. Each operation resolves its target once before backend execution, so changing the SOLIDWORKS active document cannot redirect an explicitly bound operation. `document.list`, `document.active`, `document.open`, and `document.close` use the same session registry.
