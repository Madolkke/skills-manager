# 批量 case 导入预览表设计

## 背景

批量粘贴 case 目前已经能阻止坏行提交，但用户提交前只能看到“可导入 N 条”和最多三条错误。对于从 PR backlog、表格或外部 TMS 整理来的多行 case，维护者需要在提交前快速确认每一行会变成什么：标题是否解析正确、Input/Expected output 是否串列、哪一行会阻塞。

## 外部依据

- TestRail CSV import 有 `Preview, Finalize, and Configuration Files` 步骤，用于在正式导入前确认将创建的测试用例：https://support.testrail.com/hc/en-us/articles/7101779988372-Import-test-cases-from-CSV-or-Excel
- Airtable CSV import 支持 preview sample records，让用户导入前检查字段映射和样例记录：https://support.airtable.com/docs/csv-import-extension
- GOV.UK Error Summary 要求错误摘要聚焦并链接到具体输入，错误摘要和字段旁错误文案一致。

## 方案

保留当前快速粘贴文本框和单个提交按钮，在批量模式下新增一张紧凑预览表：

- parser 返回 `previewRows`，每条非空输入行都有 `lineNumber`、`status`、解析字段和可选错误文案。
- 表格列为 `行`、`状态`、`标题`、`Input`、`Expected output`、`Notes`。
- 有效行显示 `可导入`，无效行显示 `需修正` 和错误原因。
- 表格只做预览，不做内联编辑；修正仍回到 textarea，避免第一阶段变成复杂 CSV editor。
- 无输入时显示空态，提示支持 `|` 或 tab 分隔。

视觉方向：专业、密集、可扫读，像轻量数据导入向导，而不是营销卡片。状态 chip 使用低饱和绿/红，表格保持紧凑行高和清晰边界。

## 范围

本阶段覆盖：

- 前端 parser 输出逐行预览。
- 批量 case 表单显示语义化 table。
- E2E 覆盖有效/无效行在预览中可见，并保持坏行阻止提交。
- README、体验审计和任务记录更新。

暂不覆盖：

- CSV 引号、换行转义和多 sheet 导入。
- 表格内联编辑。
- 保存导入 mapping 配置。
- 后端 raw pasted text 解析。

## 验收

- Unit 红测先失败于 `previewRows` 缺失。
- E2E 红测先失败于 `.quickCaseBatchTable` 不存在。
- 绿色后批量粘贴两行时，用户能看到每行状态和字段预览；坏行仍聚焦错误摘要并不创建部分有效 case。
