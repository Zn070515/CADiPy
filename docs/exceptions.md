# 错误语义

公共错误继承 `CadipyError`，通过稳定 `code`、operation 和 details 传递机器可读证据。类型包括参数、平台/版本、目标绑定、COM、rebuild、verification、文件和协议错误。

后端 HRESULT、SOLIDWORKS 返回码和原始异常链只留在诊断上下文，不直接成为 API/RPC 的错误契约。

## 执行与 mutation 错误

- `verification_failed`：必需 postcondition 未通过。直接 Python `CadipySession`/dispatcher 调用保留 typed `VerificationError`；RPC/MCP 返回 `ok=false` envelope。当前 CLI 的成功路径打印 `OperationResult.to_dict()` 并按 `result.ok` 返回 0/1，但 operation exception 会从 `main()` 逸出为进程级错误，而不是统一 JSON 失败响应；只有 malformed `--params-json` 会打印最小 `ok=false` JSON 并返回 2。它永远不能把该失败作为 `ok=true` 返回。
- `worker`：STA host 启动、worker loop 或断开失败。普通 command exception（包括 command 内的 backend/COM 异常）会交付给调用方，host 继续运行；timeout 的调用方收到并重新抛出内置 `TimeoutError`，host 进入 `failed`，后续提交才会得到 `WorkerError`。超时不取消正在运行的 COM 调用，调用可能仍在执行或已经改变模型。
- `transaction`：mutation 被不确定状态阻塞，或一次有边界的回滚未能证明恢复。
- `execution.phase`：`received`、`validated`、`target_resolved`、`executed`、`rebuilt`、`verified`、`committed`、`verification_failed` 或 `failed`。
- `execution.rollback_status`：`not_attempted`、`rolled_back`、`rollback_failed` 或 `state_uncertain`。`state_uncertain` 或无法验证的回滚要求关闭 session 并重新连接；在此之前不允许继续 mutation，也不自动重试。

错误结果还可包含 `state_certainty`。不要把“调用返回”解释为“模型已正确提交”：成功必须有 `ok=true` 和 `phase=committed`，而必需验证失败在 protocol envelope 中必须是失败结果。该 runtime 只提供 bounded rollback，不提供 ACID、crash-safe 或 exactly-once 语义；它也不承诺自动恢复 SOLIDWORKS 进程崩溃。

连接生命周期也属于错误处理的一部分：`connect()` 以 attach 模式开始，`launch()` 以 launch 模式开始新的 session。同一模式的 acquisition 是幂等的；冲突的 attach/launch acquisition 会抛出稳定的 `ApplicationOwnershipError`，不能重新分类已有 application。只有 CADiPy 自己 launch-owned 的实例才会在 disconnect 时退出。回滚只清理明确由 CADiPy 创建并拥有的资源。

文件持久化也有独立的安全 guard。`document.save` 和 composite `save_path` 默认使用 `overwrite=False`；目标文件已存在时，会在 `SaveAs2` 之前抛出 `FileConflictError`，原文件保持不变。只有显式 `overwrite=True` 才允许替换；如果替换后后续 operation 失败，没有 backup 时回滚必须报告不确定。
