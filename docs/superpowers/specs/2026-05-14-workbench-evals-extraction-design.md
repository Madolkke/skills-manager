# Workbench Evals Pane 组件抽离规格

## 背景

`DecisionWorkbench` 在抽离 Catalog、Inspector 和 Overview 后仍超过 2000 行。测评页是 SkillHub 的核心操作面，包含目标版本选择、候选版本验证提示、快速添加 case、手工通过/不通过队列、键盘快捷键和 case 详情。继续留在主文件里，会让后续测评体验优化风险偏高。

本任务只做结构性拆分，不改变用户可见行为。

## 用户可见行为

用户在 `测评` tab 仍能看到并操作：

- 当前 EvalSetVersion、已确认数、通过数和不通过数。
- 测评目标版本选择器，支持 current 和 candidate VariantVersion。
- candidate 版本的验证交接提示，可进入 promotion review。
- 快速添加单条/批量 case。
- review controls：筛选全部/未确认/通过/不通过，跳到未确认，未确认批量通过，清空草稿，提交 eval run。
- case queue：选择 case、标记通过/不通过、编辑、查看历史、归档。
- 键盘快捷键 `p/f/j/k` 和方向键继续生效，文本输入框内不会误触发。
- 右侧 case 详情、case 历史、恢复旧 case version 和内联编辑继续可用。

## 组件边界

新增 `WorkbenchEvalsPane`：

- 输入：case snapshot、caseResults、当前 eval target、case history、busy 和 draft 统计。
- 输出：通过回调通知父组件创建 case、更新 case、归档 case、恢复 case version、切换 eval target、记录 run、进入 promotion review。
- 组件内部负责测评页派生状态：review filter、pending cases、visible cases、keyboard queue navigation。
- 组件不直接调用 API，不维护全局 workbench mode。

`DecisionWorkbench` 保留：

- API mutation 和查询。
- `caseResults`、`selectedCaseId`、`evalTargetVersionId` 等跨 pane 状态。
- 进入 inspector action 或切换 mode 的编排。

## 非目标

- 不重做测评页视觉。
- 不改变 CSS class、按钮文案、表单字段名或快捷键。
- 不拆分 case review list 为更细组件。

## 验收标准

- `apps/web/components/evals/workbench-evals-pane.tsx` 存在。
- `DecisionWorkbench` 中不再存在内联 `function EvalsPane`。
- `DecisionWorkbench` 行数减少，`WorkbenchEvalsPane` 文件保持在 300 行以内。
- TypeScript、构建、API 测试和 E2E 全部通过。
