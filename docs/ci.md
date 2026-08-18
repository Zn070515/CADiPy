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

workflow 开始时会拒绝已有的 `SLDWORKS.exe`，使本 job 不会附着到不受控的已有实例。preflight 使用全新的 `launch(visible=False)` session 创建并拥有隐藏实例，读取 revision 和 visibility 后关闭它；集成 fixture 也只关闭 CADiPy 创建的文档和实例。测试生命周期禁止在 attach session 中再调用 `application.launch`，因为当前 backend 会把已附着的 application 重新标记为 launch-owned，断开时可能调用 `ExitApp`。

workflow 结束时只检查是否有 `SLDWORKS.exe` 残留，不执行进程级强杀。若残留，job 失败并保留证据供诊断。当前没有删除 pywin32 `gen_py` cache 的步骤；只有真实运行证明需要时才引入有边界的自愈逻辑。

## 执行安全与测试证据

session 的 strict 测试通过公开 session façade 运行；fixture 只断言可序列化结果和语义证据，并验证 executor 创建、连接、操作和断开都在同一个 STA host 线程上。100×60×3 mm 的矩形拉伸 round-trip 会创建模型、rebuild、inspect、保存、关闭、重开并再次验证。必需 verification 失败在 protocol envelope 的断言中必须是 `ok=false` 和 `verification_failed`；直接 Python session 调用仍以 typed exception 传播。附着 user-owned 实例的测试在 preflight 之后创建实例，并确认 CADiPy 断开后实例仍可用，且不走 attach-to-launch transition。

普通 portable 测试使用 fake executor 验证 FIFO、线程隔离、超时、结果序列化和 rollback state machine。这些 fake 测试证明 CADiPy 自己的边界逻辑，不证明 SOLIDWORKS COM 兼容性；只有 strict real-SOLIDWORKS gate 提供真机证据。

strict 模式由 `CADIPY_REQUIRE_REAL_SOLIDWORKS=1`（或 `--real-solidworks`）启用。缺少 Windows、Python 3.12、SOLIDWORKS、COM、Revision `34.3.2`，或 fixture/清理失败时必须 FAIL，不能静默 skip。受支持 runner 是 Windows 11 x64、labels `self-hosted`, `windows`, `x64`, `solidworks`，并使用单个串行 job；fork PR 不得在该 runner 执行。

preflight 会拒绝 job 开始前已经存在的 `SLDWORKS.exe`，因此 strict job 不会附着到该进程。除非调用方违反 attach-to-launch 的安全生命周期，fixture 只清理本次 job 明确创建并拥有的实例和文档；当前 backend 并不以代码强制拒绝该 transition。普通 command exception 会交付给调用方且 host 继续运行；timeout、worker loop/startup/cleanup failure 才会使 host failed 并拒绝后续工作。COM/进程崩溃不提供自动恢复保证，timeout 或不确定 rollback 的证据要求清理 session 并重新连接，不能用自动重试冒充成功。该执行 runtime 没有 ACID 或 exactly-once 保证。
