# 公共 API

`cadipy.execute()` 接收 registry 中的操作名和普通 Python 字典，返回不含 COM 对象的 `OperationResult`。

当前注册操作包括：

- `application.attach`
- `application.launch`
- `application.set_visibility`
- `application.info`
- `diagnostics.connect`
- `document.create_part`
- `document.list`
- `document.active`
- `document.open`
- `document.close`
- `document.inspect`
- `part.create_rectangular_extrude`
- `part.rebuild`
- `sketch.create`、`sketch.list`、`sketch.inspect`
- `sketch.add_line`、`sketch.add_rectangle`、`sketch.add_circle`、`sketch.add_arc`
- `sketch.add_relation`、`sketch.add_dimension`、`sketch.set_dimension`
- `sketch.inspect_entity`、`sketch.inspect_dimension`

操作描述、参数类型、单位、目标要求和 postconditions 均由 `cadipy.operations.registry.OPERATION_REGISTRY` 提供。CLI、RPC 和 MCP 不得重复声明操作语义。

## 持久 session

`cadipy.connect()` 返回 `CadipySession`，进入上下文时 attach 到已有 SOLIDWORKS 实例并默认保持其可见性；`cadipy.launch()` 返回显式拥有新实例的 session，默认显示窗口，可用 `visible=False` 隐藏。session 同时拥有 executor、target resolver、dispatcher 和 audit recorder。`create_part()`、`list_documents()`、`active_document()`、`open()`、`inspect()`、`rebuild()`、`close()` 和 `set_visibility()` 都通过 registry 操作，不公开 COM 对象。`application.info` 报告当前 `visible` 状态。

草图操作使用可序列化的 `SketchHandle`、`SketchEntityHandle`、`RelationHandle` 和 `DimensionHandle`。实体通过 SOLIDWORKS persistent reference 在 rebuild 与保存/重开后重新解析，并校验其属于请求的 sketch；尺寸使用带 sketch 作用域的 SOLIDWORKS 参数名并保留 `*_mm` 工程单位。引用失效时返回稳定的 `entity_reference_invalid` 错误，不按实体顺序或当前选择猜测替代对象。
