# 公共 API

`cadipy.execute()` 接收 registry 中的操作名和普通 Python 字典，返回不含 COM 对象的 `OperationResult`。

当前注册操作包括：

- `diagnostics.connect`
- `document.create_part`
- `document.inspect`
- `part.create_rectangular_extrude`
- `part.rebuild`

操作描述、参数类型、单位、目标要求和 postconditions 均由 `cadipy.operations.registry.OPERATION_REGISTRY` 提供。CLI、RPC 和 MCP 不得重复声明操作语义。
