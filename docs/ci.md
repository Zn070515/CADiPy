# Real SOLIDWORKS CI

CADiPy 的严格 SOLIDWORKS 集成测试由 `.github/workflows/solidworks-tests.yml` 提供。它既可被主 CI 调用，也可通过 GitHub Actions 的手动 dispatch 运行。

主 CI 在以下事件调用真机 gate：

- `main` push；
- 工作日 schedule；
- 同一仓库的 pull request。

来自 fork 的 pull request 不会在私有 self-hosted runner 上执行。这样可以避免不可信代码进入安装了 SOLIDWORKS 的开发机。

## Runner 要求

CADiPy runner 必须注册到 `Zn070515/CADiPy` 仓库，并具备以下 labels：

```text
self-hosted
windows
x64
solidworks
```

当前支持的宿主环境是 Windows 11 x64、Python 3.12、SOLIDWORKS 2026 SP3.2（Revision 34.3.2）。`uv` 根据仓库 `.python-version` 管理 Python；真机 workflow 不使用 `actions/setup-python`。

runner 应使用独立目录和交互式桌面 session，例如 `C:\actions-runner-cadipy`。已经配置给其他仓库的 `C:\actions-runner` 不得覆盖、迁移或复用；注册 token 只在 GitHub Settings 页面生成并在本机使用，不得写入仓库。

## 生命周期与清理

workflow 开始时会拒绝已有的 `SLDWORKS.exe`，因为 CADiPy 不应附着到或终止用户-owned 实例。preflight 使用 `launch(visible=False)` 创建并拥有隐藏实例，读取 revision 和 visibility 后关闭它；集成 fixture 也只关闭 CADiPy 创建的文档和实例。

workflow 结束时只检查是否有 `SLDWORKS.exe` 残留，不执行进程级强杀。若残留，job 失败并保留证据供诊断。当前没有删除 pywin32 `gen_py` cache 的步骤；只有真实运行证明需要时才引入有边界的自愈逻辑。
