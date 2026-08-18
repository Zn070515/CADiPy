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

响应只包含 JSON 可序列化的领域数据。MCP 是 adapter，RPC server 是 transport adapter；两者通过 session façade 提交请求，不直接持有或调用 dispatcher，也不传输 COM 引用。每个 session 的请求由一个专用 STA 执行线程按 FIFO 串行处理；Python 调用方看到的是同步请求/响应语义。

响应保留现有字段，并在 protocol version `1` 中增加结构化的 `execution` 字段：

```json
{
  "protocol": 1,
  "id": "request-1",
  "operation": "part.create_rectangular_extrude",
  "ok": true,
  "data": {"verification": "passed"},
  "error": null,
  "execution": {
    "phase": "committed",
    "state_certainty": "certain",
    "rollback_status": "not_attempted"
  }
}
```

生命周期阶段包括 `received`、`validated`、`target_resolved`、`executed`、适用时的 `rebuilt`、`verified`、`committed`，以及失败阶段 `verification_failed` 和 `failed`。必需 postcondition 失败返回 `ok=false`、错误码 `verification_failed`，不能用 `ok=true` 携带失败的 verification 字段伪装成功；mutation scope 在回滚后也可能以 `failed` 阶段返回该错误。

这里的 `ok=false` 是 protocol adapter 的 envelope 语义：`ProtocolServer.handle()` 捕获 dispatcher/session 抛出的 typed `CadipyError`，RPC 和 MCP 因而返回结构化失败响应。直接 Python 调用 `CadipySession.execute()` 或 dispatcher 时，错误会以 typed exception 传播，不会自动转换为 `OperationResult`；当前 CLI 也不把这些 operation exception 包装成统一的 JSON 失败 envelope。

`rollback_status` 只有 `not_attempted`、`rolled_back`、`rollback_failed`、`state_uncertain`。普通 command exception 会交付给调用方，host 继续处理后续 command；worker loop、startup、cleanup 失败会使 host 进入 failed 状态并拒绝后续排队请求。直接 Python host/session 调用在 timeout 时收到并重新抛出内置 `TimeoutError`；host 同时进入 failed，之后的新提交会得到 `WorkerError`。若 timeout 穿过 `ProtocolServer.handle()`，adapter 会捕获该异常并返回序列化失败 envelope。超时不会取消已经运行的 COM 调用；它可能已经改变模型。调用方必须清理 session 并重新连接，才能再次 mutation；不允许自动重试不确定的 mutation。该协议不承诺 ACID、crash-safe 或 exactly-once 语义。

持久 session 的 adapter 仍消费同一个 `OPERATION_REGISTRY` 和同一个 session façade；Dispatcher 继续由 host 独占。当前阶段新增：

```text
application.attach
application.launch
application.set_visibility
application.info
document.list
document.active
document.open
document.close
```

`application.launch` 的 `visible` 参数默认为 `true`；`application.set_visibility` 要求显式提供布尔值。`application.info` 返回当前 `visible` 状态。目标对象使用 `document_id`、`path`、`title`、`document_type` 和 `configuration` 字段。`document_id` 只在创建它的 session 内有效；RPC/MCP 不接收或返回 SOLIDWORKS COM 对象。
