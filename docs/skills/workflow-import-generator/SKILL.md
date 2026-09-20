---
name: workflow-import-generator
description: "离线将流程说明、Markdown、文本或可提取的 Word/PDF 内容转换为 SkillHub WorkflowImportBundle。仅生成 CLI 采集，支持复杂 Schema、表达式绑定与模板，交付工作流文件、静态校验和中文审阅报告。"
---

# 离线生成 CLI 工作流

根据源文档生成可审阅的工作流文件。此 Skill 完全离线，不访问命令库、MCP、解析接口或数据库，不自动导入；不执行命令、脚本、表达式函数或 TTP。

## 工作方式

1. 提取源文档事实。优先读本地 Markdown/文本；Word/PDF 使用当前环境适用的读取工具。不能可靠提取时说明缺失内容，不推测。
2. 阅读 [映射规则](references/document-mapping.md)。首次遇到新的作者结构，再按需查阅仓库的 [Schema](../../workflow-schema.md) 与 [导入协议](../../workflow-import-agent-guide.md)。这些通用协议还描述其他采集类型与在线导入，本 Skill 仅采用其中 CLI 文件格式。
3. 整理元信息、全局输入、设备角色、步骤、命令、输出契约和结论。仅生成明确的 CLI 命令；缺失契约时保留草稿。复杂数组与跨采集绑定参考 [完整示例](tests/fixtures/complex-cli.workflow-import.json) 及其 [源说明](tests/fixtures/complex-cli.md)。
4. 在用户指定目录生成 `<源名>.workflow-import.json` 与 `<源名>.workflow-import.review.md`，不改写源文档。无源名时使用 `workflow`，无指定目录时使用当前工作目录；遇到现有同名文件先选择未占用后缀。
5. 按 [校验说明](references/offline-validation.md) 执行脚本。两种模式都检查完整静态规则；先修复结构、引用和导入硬限制，再处理领域错误。仅对源文档确实缺失的内容保留占位，不为追求“通过”编造命令或类型。
6. 完整结果使用 `--mode strict` 校验；含待补全项使用默认 `draft` 并明确标记。交付文件、使用的函数契约、诊断和待确认事项。导入或运行属于后续独立任务。

## 必须遵守

- 只生成 `documentType: "workflow_import_bundle"`；Call 使用 `definitionLocalId`。不手写数据库 ID/revision 或系统来源关联，不添加不存在的 schemaVersion 字段。
- Collection 仅为 `cli`；新定义使用 `commandParameterSyntax: "angle-v1"`。`commandTemplate` 是实际具体命令，仅 `<参数>` 生成输入；固定命令无额外输入。
- 默认参数为必填 string；有明确类型时使用原类型。回显示例不等于已确认的输出 Schema，不凭示例推断事实。
- 一个完整生成结果恰有一个起始步骤。`parallelBranches` 默认 false，仅在源文档明确要求执行所有满足条件的分支时设为 true；当前外部执行器仍忽略此字段。
- 只在字段、类型和作用域均明确时生成表达式与模板。缺失输出契约时保留自然语言条件，不用未知字段拼出表达式。
- Script Step 仅承接文档明确提供的源码，不生成函数 Collection，不执行源码。
- 不把生产回显、账号、Cookie、Token、私钥等敏感内容复制进 Bundle 或报告；命令中的凭据使用待绑定输入，不保留明文。
- 离线校验无错误不等于实际命令可执行、输出可解析或流程经过运行验证。

## 本地验证入口

在仓库根目录使用已安装后端依赖的 Python，例如：

```powershell
apps/backend/.venv/Scripts/python.exe docs/skills/workflow-import-generator/scripts/validate_workflow_import_bundle.py workflow.workflow-import.json --mode strict --report-json workflow.validation.json
```

可选本地 `--expression-contract contract.json` 完全替代默认内置声明，包括空函数目录。不要为补齐契约而联网；请用户提供文件，或在报告中声明使用仓库内置规则的局限。
