# Workflow 新采集类型审计报告

**日期**：2026-08-05
**范围**：`log` 日志聚合 Collection、`config` 配置匹配 Collection 的前后端实现
**方法**：后端规则 Agent、前端交互 Agent、跨层契约 Agent 独立检查，再由主 Agent 汇总复现结果并补回归测试。

## Agent 独立结论

- **后端规则 Agent**：确认严格 `cli/log/config` 联合、v5 迁移和 executor 不支持分支已存在；独立复现了 DuckDB 动态列展开、CTE shadow、Config 捕获正则边界、表达式下标和日志列目录 OpenAPI 缺少结构等问题。
- **前端交互 Agent**：独立复现了可变 Vue key 导致输入失焦、非法 pattern 清空 captures、Config `sampleCount` 可编辑、跨调用根冲突不提示、Unicode 补全缺失和字段错误无法精确定位等问题。
- **跨层契约 Agent**：对照同一 fixture 复核 v5 `sqlDialect` 必填、错误码/selection、Config 设备角色上下文、生成器措辞和 executor unsupported 行为，确认上述前后端漂移属于真实缺陷而非测试假象。

## 审计结论

近期新增的两种 Collection 已形成严格联合模型、领域校验和编辑器基础能力，但初始实现存在前后端契约不一致及安全门禁缺口。以下问题已在本次审计实现中修复：

| 优先级 | 问题 | 处理 |
| --- | --- | --- |
| P1 | DuckDB `COLUMNS(*)` 和动态列投影绕过显式输出门禁 | 拒绝 `exp.Columns`，补充动态列回归测试 |
| P1 | Config pattern 无法解析字符类或嵌套正则中的 `>` | 前后端扫描器跟踪转义、字符类和括号深度 |
| P1 | Config 编辑器使用可变字段作为 Vue key，输入会失焦 | 改用稳定路径 key |
| P1 | pattern 暂态非法时清空已有 captures Schema | 解析失败时保留原 captures |
| P1 | 前端缺少 Config 根命令跨调用冲突校验 | 按设备角色上下文补齐校验 |
| P1 | Config `sampleCount` 可在界面编辑为非 1 | 固定为 1，仍保留设备角色选择 |
| P2 | v5 日志 `sqlDialect` 缺失时后端静默补值 | 改为严格必填 |
| P2 | Config 数组非整数下标未诊断，nullable 属性类型退化 | 增加下标门禁并保留 `null` 类型 |
| P2 | Config 字符串下标未进入 Workflow validation | 将相关诊断作为同步阻断错误 |
| P2 | 日志列目录 API OpenAPI 响应无结构 | 增加严格 response model |
| P2 | Workflow Schema 和 Import 文档遗漏 Config 联合 | 补齐字段、导入和调用约束 |
| P2 | Config 生成入口仍使用 CLI 命令措辞 | 按 log/config 类型生成准确说明，并增加生成器回归测试 |
| P2 | Config 命令树删除无确认且无法调整顺序 | 增加复用确认弹窗、稳定路径排序和移动端布局 |

## 仍需关注

- 表达式环境目前没有独立的设备上下文参数；不同设备角色下的同名 Config 根命令会被前端补全标记为歧义并隐藏，后续可设计显式上下文选择。
- 前端普通正则使用 JavaScript 兼容检查，Python 专属构造交由后端 `re` 校验；两端扫描器已经共享转义、字符类和括号深度规则，但未在浏览器内执行 Python 正则。
- 1440/1024/768/375 的真实浏览器截图未纳入自动化门禁；本次补充了窄屏 CSS 的递归命令树换行规则，后续应在发布前做人工视觉回归。
- 全仓库 mypy 仍有既有 mixin 类型错误；本次变更模块定向 mypy（`log_sql.py`、Config parser、expression checker/workflow、Workflow view DTO）均无错误。

## 测试证据

- 后端完整测试：`285 passed, 176 skipped`；架构测试：`13 passed`。
- 前端完整测试：`27` 个文件、`186 passed`；`lint`、`vue-tsc` 和生产构建通过（保留既有 chunk 体积警告）。
- 后端 `ruff`、Python `compileall` 和变更模块定向 mypy：通过。
- `git diff --check`：通过；历史审计报告 `docs/workflow-code-audit-2026-08-01.md` 保留原结论，未被改写。
