---
name: workflow-import-generator
description: "从流程说明文档、Markdown、文本或可提取的 Word/PDF 内容生成并校验 SkillHub WorkflowImportBundle。用于将排障、运维或业务流程转为可导入工作流，并输出待补全执行契约的审阅报告。"
---

# 文档工作流导入

将用户提供的流程说明转换为可审阅的 `WorkflowImportBundle`，默认只生成和校验文件。不要调用导入 API，除非用户在当前请求中明确要求导入。

## 执行流程

1. 读取源文档并提取文本。优先使用用户提供的内容或本地 Markdown/文本；对可访问的 `.docx` 或 PDF 使用适用的文档读取工具。无法可靠读取时，请用户提供文本，不要猜测内容。
2. 阅读 [导入协议](../../workflow-import-agent-guide.md) 和 [Schema](../../workflow-schema.md)。首次处理新的工作流形态时，参考 [现有 Bundle](../../examples/executor-integration-workflow-import.json)。
3. 先建立文档到节点、输入、设备角色、采集、条件、跳转和结论的映射。采用 [映射规则](references/document-mapping.md)，并记录无法确认的信息。
4. 生成 `<源文件名>.workflow-import.json` 和 `<源文件名>.workflow-import.review.md`；不要改写源文档。没有可用文件名时，先征求输出路径。
5. 运行 `scripts/validate_workflow_import_bundle.py <bundle-path>`。修复所有结构或引用错误；保留脚本报告的 CLI 占位项，并在审阅报告中说明。
6. 交付两个文件、校验结果和待补全事项。只有用户明确要求、提供 `skill_id` 与操作者身份后，才执行 `POST /api/skills/{skill_id}/workflow/import`；该请求不可自动重试。

## 输出约束

- 始终生成 `documentType: "workflow_import_bundle"`，并在 Call 中使用 `definitionLocalId`。
- 不生成 `workflow.id`、`workflow.revision`、Collection 的 `id`/`revision`/`forkedFrom`、权限、Owner、Tag 历史或版本历史。
- 为节点、输入、角色、Call、输出和跳转生成稳定且请求内唯一的 ID；`localId` 必须唯一，且每个 Call 必须引用存在的 Collection。
- 仅将文档明确给出的命令、输入、输出和 JSON Schema 写入 CollectionDefinition。缺少执行契约时生成 CLI 占位定义，使用空 `commandTemplate`，并把待补全项写入审阅报告。
- 仅在输出字段与类型都已确认时生成 `conditionExpression`。否则保留文档原意至 `conditionText`，令 `conditionExpression` 为空。
- 避免将生产回显、账号、Cookie、Token、私钥或其他敏感数据写入 Bundle、样例或审阅报告。

## 校验和导入

校验脚本仅验证 Bundle 的结构、持久化字段禁令和引用完整性。空 `commandTemplate` 表示“可导入草稿但尚不可同步执行”，不是结构错误。补全命令和 Schema 后，再按仓库的完整 Workflow 校验规则检查领域错误。

导入属于有副作用操作。导入前再次展示 Bundle 路径与目标 Skill；导入失败时返回服务端响应，不要重试或重建 ID。
