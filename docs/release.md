# 发布纪律

版本号单一来源为 `src/cadipy/__init__.py`。发布前必须运行 portable quality gates、普通集成模式、严格 real-SW gate（在配置环境可用时）、wheel/sdist 内容审计和文档构建。

发布包不得包含模板遗留的非 CAD 源码、演示文稿 fixture、内部路径或开发日志。
