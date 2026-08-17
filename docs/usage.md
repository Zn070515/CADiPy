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

持续操作同一个 SOLIDWORKS 工程时使用持久 session。`connect()` 严格 attach 到已运行实例；需要 CADiPy 创建并拥有新实例时显式使用 `launch()`。session 结束后其中的 `document_id` 失效，已保存文档应使用路径、标题、类型或 configuration 重新绑定。

```python
from cadipy import connect

with connect() as cad:
    part = cad.create_part()
    cad.rebuild(target=part)
    inspection = cad.inspect(target=part)
```

文档目标必须显式提供 `document_id`、`path`、`title`、`document_type` 或 `configuration` 中的至少一项。每个操作开始前只解析一次目标；SOLIDWORKS 当前 active document 改变不会把明确目标切换到另一文档。`document.list`、`document.active`、`document.open` 和 `document.close` 也通过同一 session registry 工作。

CLI 使用 `cadipy check` 或 `cadipy server status` 检查执行环境；统一操作可通过 `cadipy operation <name> --params-json '<json>'` 调用。
