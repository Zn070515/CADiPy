# CADiPy 项目开发说明

CADiPy 是面向 SOLIDWORKS 的 agent automation 工程：公开 API 使用稳定的 CAD 领域对象和显式单位，执行后端通过 `SolidWorksExecutor` 隔离 Python COM 细节，并为未来 C# Worker 保留可替换边界。

## spec 与 plan 审核纪律

- 任何跨模块能力先形成设计文档和分阶段实施计划。
- 文档至少按契约、错误路径、资源生命周期、可测试性和长期维护性审核两轮。
- 计划完成后才进入实现；实现中的范围变化必须同步更新设计文档、计划和 CHANGELOG。

## 环境要点

- Windows + PowerShell 是本地开发环境；跨平台纯模块检查可在 Linux CI 执行。
- 使用 `uv` 管理 Python 3.12 环境：`uv run python`、`uv run pytest`、`uv run cadipy`。
- Python 子进程统一设置 `PYTHONIOENCODING=utf-8`，避免 Windows 终端编码差异。
- SOLIDWORKS 集成测试默认允许在无 SW 环境中 skip；自托管或显式 `CADIPY_REQUIRE_REAL_SOLIDWORKS=1` 时缺少 SW、COM 不通或版本不符必须 FAIL。
- 每次 COM 验证后确认测试创建的文档已关闭，临时 `.SLDPRT` 已清理，且没有遗留 `SLDWORKS.EXE` 进程或锁定文件。

## 工程开发纪律

### 分支纪律

- 所有功能、修复、文档、依赖和 CI 变更先在分支完成，禁止直接在 `main` 上开发。
- 分支使用 `feat/`、`fix/`、`docs/` 或 `build/` 前缀。
- 提交前确认只包含当前任务的变更；合并前必须通过 ruff、mypy、pytest、文档构建和适用的真实 SOLIDWORKS 门禁。

### 领域和执行边界

- 公开 CAD API 不泄漏 pywin32、COM 对象、SOLIDWORKS 内部米/弧度或本地化 UI 名称。
- 长度公开使用 `*_mm`，角度公开使用 `*_deg`；转换只发生在后端边界。
- CLI、RPC、MCP 必须消费同一个 `OpSpec` 注册表和 dispatcher；MCP 只是 adapter。
- 业务能力放在 `domain/`、`operations/`、`verification/`；SOLIDWORKS 细节只放在 `backends/solidworks/`。
- 所有文档、草图、特征和 COM 资源都必须有明确的关闭、失败清理和审计路径。

### 文档与发布纪律

- 代码行为变化必须同步 README、`docs/` 和 CHANGELOG。
- 版本号单一来源为 `src/cadipy/__init__.py`，构建配置通过 Hatch 读取；版本升级单独提交。
- 发布只能由 GitHub Actions 的 release 链触发，不绕过质量门禁手动上传。
- `docs/development/` 和 `docs/superpowers/` 是内部研究与计划目录，默认不纳入发布文档；对外契约文档必须位于 README 或 `docs/` 发布导航内。

### 提交纪律

- 小步提交，使用 `feat:`、`fix:`、`docs:`、`build:`、`test:` 或 `chore:` 前缀。
- 提交前运行 `git status`、`git diff --check` 和与变更范围匹配的验证命令。
- 不修改或删除用户已有的无关工作树变更。
