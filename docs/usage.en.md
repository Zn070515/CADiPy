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
