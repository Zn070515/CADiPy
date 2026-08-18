# 错误语义

公共错误继承 `CadipyError`，通过稳定 `code`、operation 和 details 传递机器可读证据。类型包括参数、平台/版本、目标绑定、COM、rebuild、verification、文件和协议错误。

后端 HRESULT、SOLIDWORKS 返回码和原始异常链只留在诊断上下文，不直接成为 API/RPC 的错误契约。

## 执行与 mutation 错误

- `verification_failed`：必需 postcondition 未通过。Python façade 保留 typed `VerificationError`；RPC、MCP 和 CLI 返回 `ok=false`。它永远不能作为 `ok=true` 返回。
- `worker`：STA host 启动、worker、断开或超时失败。超时不取消正在运行的 COM 调用；调用可能仍在执行或已经改变模型。
- `transaction`：mutation 被不确定状态阻塞，或一次有边界的回滚未能证明恢复。
- `execution.phase`：`received`、`validated`、`target_resolved`、`executed`、`rebuilt`、`verified`、`committed`、`verification_failed` 或 `failed`。
- `execution.rollback_status`：`not_attempted`、`rolled_back`、`rollback_failed` 或 `state_uncertain`。`state_uncertain` 或无法验证的回滚要求关闭 session 并重新连接；在此之前不允许继续 mutation，也不自动重试。

错误结果还可包含 `state_certainty`。不要把“调用返回”解释为“模型已正确提交”：成功必须有 `ok=true` 和 `phase=committed`，而必需验证失败必须是失败结果。该 runtime 只提供 bounded rollback，不提供 ACID、crash-safe 或 exactly-once 语义。

连接生命周期也属于错误处理的一部分：`connect()` 附着的已有 SOLIDWORKS 实例不是 CADiPy 所有，session 清理不会终止它；`launch()` 创建且拥有的实例才可由 CADiPy 关闭。回滚只清理明确由 CADiPy 创建并拥有的资源。
