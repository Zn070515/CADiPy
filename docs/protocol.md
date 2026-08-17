# 协议

协议版本为 `1`。请求使用：

```json
{
  "protocol": 1,
  "id": "request-1",
  "operation": "part.create_rectangular_extrude",
  "params": {"width_mm": 100.0, "height_mm": 60.0, "depth_mm": 3.0}
}
```

响应只包含 JSON 可序列化的领域数据。MCP 是 adapter，RPC server 是 transport adapter；两者都调用同一个 Dispatcher，不传输 COM 引用。

持久 session 的 adapter 仍消费同一个 `OPERATION_REGISTRY` 和同一个 session-owned Dispatcher。当前阶段新增：

```text
application.attach
application.launch
application.info
document.list
document.active
document.open
document.close
```

目标对象使用 `document_id`、`path`、`title`、`document_type` 和 `configuration` 字段。`document_id` 只在创建它的 session 内有效；RPC/MCP 不接收或返回 SOLIDWORKS COM 对象。
