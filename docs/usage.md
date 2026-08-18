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

## 执行安全契约

每个 `CadipySession` 只拥有一个专用 STA 执行线程。executor、dispatcher、目标 registry、连接/断开生命周期和 Python COM 调用都在该线程上运行；公共 API 只返回可序列化的领域值，不返回 COM 对象。`execute()` 是同步 façade：调用方等待结果，多个并发调用会按 session 的队列顺序串行执行，不会并行进入 SOLIDWORKS。

下面是当前的 100×60×3 mm 合同示例：

```python
from cadipy import launch

with launch(visible=False) as cad:
    result = cad.execute(
        "part.create_rectangular_extrude",
        params={
            "plane": "Front Plane",
            "width_mm": 100.0,
            "height_mm": 60.0,
            "depth_mm": 3.0,
        },
    )
    if not result.ok:
        raise RuntimeError(result.error)
```

结果中的 `execution` 报告记录生命周期：成功通常依次经过 `received`、`validated`、`target_resolved`、`executed`、适用时的 `rebuilt`、`verified`，最后为 `committed`。失败结果必须是 `ok=false`，并可报告 `verification_failed` 或 `failed` 阶段、`state_certainty` 和 `rollback_status`。必需 postcondition 失败的错误码固定为 `verification_failed`；旧式的 `ok=true` 加 `verification="failed"` 不代表成功。mutation scope 内的验证失败可能在回滚后以 `failed` 阶段返回，但仍绝不能是成功结果。

超时只停止等待，不取消正在执行的 Python 或 COM 调用。运行中的调用可能已经修改模型，因此 host 会进入失败状态，排队中的调用会被拒绝；超时或结果不明确后，必须先结束 session 并重新连接，再进行 mutation。CADiPy 不会自动重试不确定的 mutation。

mutation scope 只做有边界的一次回滚尝试。`rollback_status` 的值为 `not_attempted`、`rolled_back`、`rollback_failed` 或 `state_uncertain`。只有回滚观察得到验证时才报告 `rolled_back`；回滚失败或无法证明状态时，后续 mutation 必须等 session 清理并重新连接。该机制不是 ACID 事务、不是 crash-safe 事务，也不提供 exactly-once 保证。

`connect()` 附着到已有的 SOLIDWORKS 实例，session 结束时只释放 CADiPy 的引用，不终止该实例。`launch()` 创建并拥有的新实例可以由 CADiPy 在断开时关闭；回滚时也只清理 CADiPy 创建且明确归其所有的文档或资源。

持续操作同一个 SOLIDWORKS 工程时使用持久 session。`connect()` 严格 attach 到已运行实例，默认保持其当前窗口可见性；需要 CADiPy 创建并拥有新实例时显式使用 `launch()`，默认显示窗口。自动化场景可使用 `launch(visible=False)`。session 结束后其中的 `document_id` 失效，已保存文档应使用路径、标题、类型或 configuration 重新绑定。

```python
from cadipy import connect

with connect() as cad:
    part = cad.create_part()
    cad.rebuild(target=part)
    inspection = cad.inspect(target=part)
```

应用程序可见性是 application-level 契约，不涉及文档或模型实体可见性：

```python
from cadipy import launch

with launch(visible=True) as cad:
    part = cad.create_part()
    cad.set_visibility(False)
    cad.set_visibility(True)
```

`application.info` 返回当前 `visible` 状态；协议客户端也可调用 `application.set_visibility`。公共 API 不返回 SOLIDWORKS COM 对象。

文档目标必须显式提供 `document_id`、`path`、`title`、`document_type` 或 `configuration` 中的至少一项。每个操作开始前只解析一次目标；SOLIDWORKS 当前 active document 改变不会把明确目标切换到另一文档。`document.list`、`document.active`、`document.open` 和 `document.close` 也通过同一 session registry 工作。

参数化草图通过同一个 session 的 `execute()` 组合：`sketch.create` 创建平面草图，`sketch.add_line` / `sketch.add_rectangle` / `sketch.add_circle` / `sketch.add_arc` 返回可序列化实体句柄，随后用 `sketch.add_relation`、`sketch.add_dimension` 和 `sketch.set_dimension` 修改模型。所有长度仍使用毫米；实体保存/重开后使用 persistent reference 重新解析。

CLI 使用 `cadipy check` 或 `cadipy server status` 检查执行环境；统一操作可通过 `cadipy operation <name> --params-json '<json>'` 调用。
