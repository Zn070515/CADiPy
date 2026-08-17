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
