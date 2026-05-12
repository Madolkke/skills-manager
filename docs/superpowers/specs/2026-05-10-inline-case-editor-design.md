# 测评 case 详情内联编辑设计

日期：2026-05-10

## 背景

当前 SkillHub 的测评页已经有 review queue、快速添加和 case history，但编辑 case 仍主要通过右侧 inspector。用户在测评时发现 input 或 expected output 不严谨，需要离开正在看的 case 内容去右侧表单修改，保存后再回到队列。这会打断“看 case -> 判断 -> 修正测评集 -> 继续测评”的主流程。

## 借鉴模式

- Linear 的 issue 详情允许直接点击标题和描述进行 inline editing，并用 `Peek` 在列表中快速查看详情，降低切换成本。
- Airtable 的 record detail sidesheet 把“列表选择记录”和“在详情中编辑字段”放在同一个工作流里，字段是否可编辑由界面配置控制。
- TestRail 的三栏执行视图把 case 详情、结果提交和 `Pass & Next` 放在同一上下文，适合连续处理测试用例。

## 设计目标

1. 用户在 `测评` 页选中某个 case 后，中间详情面板就是该 case 的工作台。
2. 详情面板默认展示 `Input`、`Expected output`、`Notes`、case version 和 snapshot 位置。
3. 用户点击 `编辑` 后在同一面板修改 title、input、expected output、notes。
4. 保存调用现有 `PATCH /api/eval-cases/{case_id}`，继续保持“编辑即创建新 case version + 新 EvalSetVersion”的历史语义。
5. 保存成功后刷新页面数据，保持该 case 选中，用户可以继续手工通过/不通过或打开历史。

## 非目标

- 不做 autosave。SkillHub 的 case 编辑会生成新版本，必须显式保存。
- 不做批量编辑。批量新增已由 quick add 解决，本轮只优化单 case 修正。
- 不做审批状态。TestRail 的 case approval 有价值，但属于权限和多用户阶段。

## 交互细节

- 空状态：无 case 时提示先添加测试用例。
- 查看态：详情面板顶部显示 case title、`case vN`、位置；右上角提供 `编辑`、`历史`、`归档`。
- 编辑态：表单字段在详情面板内展开，按钮为 `保存为新版本` 和 `取消`。
- 保存中：沿用全局 `busy` 禁用提交，避免重复写入。
- 历史态：用户点击 `历史` 后仍显示现有 `CaseHistoryPanel`，恢复旧版本行为不变。

## 测试策略

- 新增 E2E：导入 skill -> 添加 case -> 在测评详情面板点击编辑 -> 修改字段 -> 保存为新版本 -> 断言队列和详情中出现新标题、新 input、新 expected output。
- 保留现有 inspector 编辑 E2E，确保旧入口未回归。
- 完整验证仍运行 API pytest、web typecheck、build、Playwright E2E 和 `git diff --check`。
