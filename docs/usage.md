# 使用方式

公开长度字段必须带 `_mm`，角度字段必须带 `_deg`。例如矩形拉伸使用 `width_mm`、`height_mm` 和 `depth_mm`；不把 SOLIDWORKS 内部米/弧度暴露到协议或 API。

```python
from cadipy import execute

result = execute(
    "part.create_rectangular_extrude",
    params={"width_mm": 100.0, "height_mm": 60.0, "depth_mm": 3.0},
)
```

执行结果区分 API 调用、rebuild、verification 和保存/重开证据。真实 CAD 状态以 `verification_report` 为准。

CLI 使用 `cadipy check` 或 `cadipy server status` 检查执行环境；统一操作可通过 `cadipy operation <name> --params-json '<json>'` 调用。
