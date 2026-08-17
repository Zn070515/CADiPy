# CADiPy SOLIDWORKS 工程设计文档

## 1. 目标与当前工作范围

CADiPy 是一个独立的 SOLIDWORKS agent automation 项目。当前实施阶段建立可长期维护的 Python 控制面、统一操作契约、SOLIDWORKS 执行边界、真实几何验证、诊断和发布纪律。

C# Worker 是已确定的长期执行后端。本阶段不实现 C# Worker，但从现在起所有 Python COM 细节必须封装在 `SolidWorksExecutor` 后端边界内。

## 2. 分层架构

```text
Agent / CLI / RPC / MCP
            │
            ▼
       OpSpec registry
            │
            ▼
   validation + dispatcher
            │
            ▼
   SolidWorksExecutor boundary
       ┌────┴────┐
       ▼         ▼
 Python COM   future C# Worker
```

- `domain/`：文档、目标、句柄、单位和稳定错误。
- `operations/`：`OpSpec`、参数校验、dispatcher 和 postcondition 声明。
- `backends/solidworks/`：COM apartment、应用连接、文档、几何和保存实现。
- `protocol/`：结果模型、服务器、客户端和 MCP adapter。
- `verification/`：可解释的几何后置条件报告。
- `diagnostics/`：环境能力与 strict gate。
- `audit/`：操作生命周期和资源事件记录。

## 3. 公开契约

公开 API 不暴露 COM 对象、pywin32 类型、本地化 UI 名称或内部单位。长度统一使用 `*_mm`，角度统一使用 `*_deg`；米、弧度和 COM 枚举只允许出现在后端实现。

所有写操作必须显式解析目标，禁止以当前 UI 焦点作为身份。目标应能由 document id、绝对路径、标题和配置组合解析，并在歧义时失败。

CLI、RPC、MCP 和 Python API 都从同一注册表读取操作定义。MCP 只负责适配，不包含 CAD 业务逻辑。

## 4. 真实几何纵向契约

长期 integration fixture 必须完成：

1. 创建 Part；
2. 创建 Sketch；
3. 绘制 `100 × 60 mm` 矩形；
4. 拉伸 `3 mm`；
5. rebuild；
6. 读取真实 API 状态并验证实体数量、包围盒、草图、特征、尺寸、抑制状态和 rebuild 结果；
7. 保存临时 `.SLDPRT`；
8. 关闭并重新打开；
9. rebuild 后再次验证同一 postcondition；
10. 无论成功失败都清理文档和临时文件。

普通环境缺少 SOLIDWORKS 时允许 skip。显式 strict gate 或 self-hosted gate 中，缺少应用、COM 不通或版本不符合要求必须 FAIL。

## 5. 资源与错误

COM apartment、应用实例、文档、草图和特征都必须有明确所有权。失败路径要释放当前资源并保留可诊断上下文。稳定错误至少包括 invalid argument、target not found、unsupported version、COM unavailable、document type mismatch、rebuild failure 和 verification failure。

## 6. 质量与发布

每个能力都必须配套纯测试、适用的真实集成测试、文档、错误路径和审计事件。提交前运行 ruff、format、mypy、pytest、MkDocs、构建和 wheel 内容检查。版本号只从 `src/cadipy/__init__.py` 读取；发布物不得包含内部路径、生成文件或非 CAD 产品历史。
