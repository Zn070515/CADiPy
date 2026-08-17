# CADiPy 文档

CADiPy 的当前实施阶段建立一套长期维护的 SOLIDWORKS agent automation 边界：公共控制面使用领域值和统一 OpSpec，执行面由 Python COM backend 承担，未来 C# Worker 遵循同一接口。

核心入口：

- [当前工作范围与使用方式](usage.md)
- [公共 API 与操作](api/index.md)
- [协议与 MCP adapter](protocol.md)
- [兼容性与 strict real-SW gate](compatibility.md)
- [错误语义](exceptions.md)
- [迁移记录](migration.md)
