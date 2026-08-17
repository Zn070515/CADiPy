# 公共 API

`cadipy.execute()` 接收 registry 中的操作名和普通 Python 字典，返回不含 COM 对象的 `OperationResult`。

当前注册操作包括：

- `application.attach`
- `application.launch`
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

操作描述、参数类型、单位、目标要求和 postconditions 均由 `cadipy.operations.registry.OPERATION_REGISTRY` 提供。CLI、RPC 和 MCP 不得重复声明操作语义。

## 持久 session

`cadipy.connect()` 返回 `CadipySession`，进入上下文时 attach 到已有 SOLIDWORKS 实例；`cadipy.launch()` 返回显式拥有新实例的 session。session 同时拥有 executor、target resolver、dispatcher 和 audit recorder。`create_part()`、`list_documents()`、`active_document()`、`open()`、`inspect()`、`rebuild()` 和 `close()` 都通过 registry 操作，不公开 COM 对象。
