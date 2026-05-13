# Workbench Overview Pane 组件抽离规格

## 背景

`DecisionWorkbench` 在抽离 Catalog 和 Inspector 后仍接近 2600 行。概览页承载默认分发、验证分数、设置、权限、治理、首次验证引导和 bundle preview，是主工作区信息密度最高的页面。继续把它留在主文件里，会让后续 UI 调整和信息架构优化变得脆弱。

本任务只做结构性拆分，不改变用户可见行为。

## 用户可见行为

用户在 `概览` tab 仍能看到并操作：

- 空 skill 状态下的 `SkillLaunchpad`，可导入标准 Skill bundle 或创建空 skill。
- 默认分发 hero，包含 default variant label、summary、tags 和最近验证分数。
- 变体数、当前版本、测评集版本、最近分数四个 metric。
- Skill 设置、访问控制、治理危险区。
- 首次验证引导，可继续跳转新增 case、打开测评、打开历史。
- Skill bundle 文件列表、`SKILL.md` 预览、追加版本、比较版本和打开详情入口。

## 组件边界

新增 `WorkbenchOverviewPane`：

- 输入：skill detail、default variant、latest run、score、case 数量、actor、busy、import preview。
- 输出：通过回调通知父组件执行导入、新建、更新 skill、授权、撤销、归档、打开 diff、切换 mode 和切换 inspector action。
- 组件内部只负责概览页展示、bundle preview 读取和空态/非空态分支。
- 组件不直接调用 API，不维护全局状态。

新增 `Metric` 共享组件：

- 保留原有 `linearMetric` className 和 tone 语义。
- 供 Overview、Diff、History 继续共用，避免复制内联组件。

`DecisionWorkbench` 保留：

- API mutation 和查询。
- mode、selected skill、selected case、run filters、diff state 等编排状态。
- `parseSkillMetadata`、diff 和 import preview 等主工作台仍需的工具函数。

## 非目标

- 不重做概览页视觉设计。
- 不改变 CSS class、按钮文案、表单字段名或导航入口。
- 不把 SkillSettings、Access、Governance 继续拆分。

## 验收标准

- `apps/web/components/overview/workbench-overview-pane.tsx` 存在。
- `DecisionWorkbench` 中不再存在内联 `function OverviewPane`。
- `DecisionWorkbench` 行数减少，`WorkbenchOverviewPane` 文件保持在 300 行以内。
- TypeScript、构建、API 测试和 E2E 全部通过。
