# Form Error Count 设计

日期：2026-05-17

## 背景

SkillHub 已经用 `ValidatedForm` 统一了错误摘要、字段旁错误、`aria-invalid` 和摘要链接聚焦。但当前摘要只写“修正后再提交”，没有告诉用户本次提交一共有几个字段需要修正。对 SkillHub 这种表单密集的工作台来说，用户会在 Launchpad、快速添加 case、批量导入、访问控制、promotion decision 等不同上下文里遇到错误；摘要里缺少数量，会让用户先扫一遍列表才能知道工作量。

本轮只增强错误摘要文案，不改字段校验规则、不改视觉系统、不新增表单状态持久化。

## 外部实践

- GOV.UK / MOJ 的错误摘要模式强调：提交后聚焦错误摘要，摘要要用用户能理解的语言概括问题，并列出可点击的字段错误。SkillHub 已经做到聚焦和链接，本轮补“问题数量”作为状态可见性。
- NN/g usability heuristics 的“系统状态可见”适用于错误恢复：用户应该立刻知道还有多少问题，而不是自己数列表项。
- Linear / GitHub 这类工作台产品会在批量操作或校验失败时明确数量，例如 failed checks、unresolved comments。SkillHub 适配为表单错误摘要直接显示字段错误数量。

## 本轮方案

在 `FormErrorSummary` 的说明段落中加入错误数量：

- 1 条错误：`1 个字段需要修正。修正后再提交。`
- 多条错误：`N 个字段需要修正。修正后再提交。`

保留现有行为：

- `role="alert"`
- 提交后聚焦 summary
- summary 链接回字段
- 字段旁错误和 `aria-invalid`
- API `field_errors` 与客户端 required 错误共用同一个摘要组件

## 不做

- 不新增全局 toast 统计。
- 不在每个 tab 或 inspector header 上显示错误 badge。
- 不改变错误排序。
- 不合并重复字段错误；当前每个 field error 仍按提交时收集顺序展示。

## 成功标准

1. 提交空白 Launchpad 新建 skill 时，错误摘要显示 `6 个字段需要修正。修正后再提交。`
2. 摘要仍包含每条字段错误链接，点击 `填写 Skill ID` 后仍聚焦 `slug` 字段。
3. 所有现有表单错误 E2E 继续通过。
4. 完整前端、后端、构建和 E2E 验证通过。
