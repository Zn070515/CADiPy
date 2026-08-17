# 兼容性

当前严格基线：Windows 11 x64、Python 3.12、SOLIDWORKS 2026 SP3.2、COM revision `34.3.2`、pywin32 312 或兼容更新版本。

| 能力 | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 |
| --- | --- | --- | --- | --- |
| portable test suite | Tested | Tested | Tested | Tested |
| real SOLIDWORKS contract | Not validated | Not validated | Tested | Not validated |

portable matrix 的当前证据为每个版本 `25 passed, 1 deselected`；real SOLIDWORKS strict contract 在 Python 3.12、SOLIDWORKS 2026 SP3.2、revision `34.3.2` 下通过。未标记为 Tested 的组合不视为已支持证据。

普通 `solidworks` 集成测试在缺少 SOLIDWORKS 或 COM 时带明确原因 skip。`--real-solidworks` 或 `CADIPY_REQUIRE_REAL_SOLIDWORKS=1` 启用 strict gate：缺少程序、COM 连接失败、Python/版本不符合或纵向契约失败都会 FAIL。

长期 C# Worker 的兼容性由同一 `SolidWorksExecutor` port 和 versioned protocol 约束；本轮不包含 C# 实现。
