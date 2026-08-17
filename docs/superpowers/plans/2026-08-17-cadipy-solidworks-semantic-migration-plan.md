# CADiPy SOLIDWORKS 分阶段实施计划

## 当前里程碑

建立独立 CADiPy 工程基础、统一操作契约、可替换 SOLIDWORKS 执行边界和真实几何纵向验证。C# Worker 作为长期确定后端保留接口，本阶段不实现其代码。

## 阶段 1：工程基线与领域模型

- 确认根目录 Git、分支、remote、Python 3.12 和 uv 环境。
- 建立 `domain/`：DocumentType、DocumentHandle、TargetBinding、稳定异常和显式单位转换。
- 为长度、角度、目标解析和错误码建立纯测试。
- 保持公开模型不包含 COM 类型和内部单位。

验收：纯领域测试通过，所有公开字段使用明确单位后缀。

## 阶段 2：执行边界与 SOLIDWORKS 后端

- 定义运行时可替换的 `SolidWorksExecutor` 协议。
- 实现 Python COM 后端，隔离 apartment、应用连接、文档生命周期、草图、几何、重建和保存。
- 后端返回领域句柄和报告，不把 COM 对象泄漏到 API、协议或 adapter。
- 记录官方 API 使用依据与本地运行时差异。

验收：COM 后端可连接应用、创建 Part、关闭文档，并通过后端契约测试。

## 阶段 3：统一操作与协议适配

- 建立唯一 `OPERATION_REGISTRY`。
- 为 diagnostics、Part 创建、文档检查、重建和矩形拉伸定义 `OpSpec`。
- 由同一 dispatcher 服务 Python API、CLI、RPC 和 MCP。
- 为参数校验、目标约束、结果序列化和错误映射建立测试。

验收：所有入口的操作名称和参数来自同一注册表，不存在平行定义。

## 阶段 4：真实几何与 strict gate

- 实现 Part → Sketch → `100 × 60 mm` 矩形 → `3 mm` 拉伸 → rebuild。
- 实现 postcondition verification，检查实体、尺寸、特征状态和 rebuild。
- 保存临时 `.SLDPRT`，关闭、重新打开、rebuild 并再次验证。
- 普通环境允许 skip；显式 strict 或 self-hosted 环境缺失依赖必须 FAIL。

验收：普通真实集成测试和 strict real-SW 测试均在可用环境串行通过。

## 阶段 5：诊断、审计和工程发布面

- 建立环境报告、版本能力、资源生命周期和操作审计事件。
- 清理非 CAD 产品源码、fixture、第三方声明、脚本、旧元数据和旧工作流。
- 更新 README、CHANGELOG、API、协议、兼容性、弃用、安全、贡献和发布文档。
- CI 分为纯质量门禁、打包门禁、文档门禁和 strict real-SW 门禁。

验收：wheel/sdist 内容只有 CADiPy；文档和 CI 使用根目录项目；全仓库词汇审计无旧产品标识。

## 持续纪律

- 后续开发禁止使用 Git worktree。
- 每项工作从 `main` 创建新分支，并直接在仓库根目录完成。
- 代码、契约、测试、文档和 CHANGELOG 同步演进。
- 不以通过 mock 代替真实 SOLIDWORKS 验证；不以 skip 代替 strict gate。
