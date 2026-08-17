# CADiPy

CADiPy 是面向长期维护的 SOLIDWORKS agent automation 工程。Python 负责公共 API、OpSpec/schema、目标安全、协议适配、诊断、审计和验证；SOLIDWORKS 执行细节位于可替换的 `SolidWorksExecutor` 边界之后。

当前工作范围包括：

- Python COM executor，未来 C# Worker 使用同一执行器边界；
- 统一的 domain / operations / backends / protocol / verification / diagnostics / audit 结构；
- 所有公开长度使用 `*_mm`，角度使用 `*_deg`，内部米/弧度仅存在于 SolidWorks backend；
- CLI、RPC、MCP 共同消费同一个 OpSpec registry 和 dispatcher；
- P1 参数化草图核心：可序列化 Sketch entity identity、line/rectangle/circle/arc、关系、尺寸和 save/reopen 重新解析；
- 真实 SOLIDWORKS 纵向契约：Part → Sketch → 100×60 mm 矩形 → 3 mm 拉伸 → rebuild → postcondition verification → SLDPRT round-trip。

## 开发

```powershell
uv sync --extra dev
uv run pytest tests -q
uv run pytest -m "not solidworks" --cov=cadipy.domain --cov=cadipy.operations --cov=cadipy.protocol --cov=cadipy.verification --cov=cadipy.diagnostics --cov=cadipy.audit --cov-fail-under=85 -q
uv run pytest tests/integration/solidworks -m solidworks -q
```

在受支持的 Windows + SOLIDWORKS 环境运行严格门禁：

```powershell
$env:CADIPY_REQUIRE_REAL_SOLIDWORKS = '1'
uv run pytest tests/integration/solidworks -m real_solidworks --real-solidworks -q
Remove-Item Env:CADIPY_REQUIRE_REAL_SOLIDWORKS -ErrorAction SilentlyContinue
```

缺少 SOLIDWORKS、COM 不通或版本不符合要求时，严格门禁失败；普通集成模式才允许带原因 skip。

## API 示例

```python
from cadipy import execute

result = execute(
    "part.create_rectangular_extrude",
    params={"width_mm": 100.0, "height_mm": 60.0, "depth_mm": 3.0},
)
assert result.ok
assert result.data["verification"] == "passed"
```

连续操作同一 SOLIDWORKS 文档时使用持久 session：`connect()` 严格连接已有实例并默认保持窗口状态，`launch()` 显式创建并拥有新实例且默认显示窗口；自动化场景可使用 `launch(visible=False)`。

```python
from cadipy import connect

with connect() as cad:
    part = cad.create_part()
    cad.rebuild(target=part)
```

详细契约见 [文档首页](docs/index.md)、[API](docs/api/index.md)、[协议](docs/protocol.md) 和 [兼容性](docs/compatibility.md)。
