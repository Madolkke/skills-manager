# Workbench E2E 拆分设计

## 背景

`apps/web/e2e/skills-workbench.spec.ts` 已超过 1000 行，继续把新增产品流测试塞进同一个文件，会让后续维护、定位失败和审查 diff 变慢。TASK-076 只做测试组织重构，不改变任何用户可见行为。

## 目标

- 把历史、Run matrix、saved view、run comparison、case version history 相关测试从 `skills-workbench.spec.ts` 拆到专门规格文件。
- 保持测试标题、断言和辅助函数行为不变，Playwright 全量测试数量不减少。
- 原文件仍保留导入、创建、权限、治理、命令菜单、批量 case、候选版本和移动端基础流。
- 不新增产品功能，不改生产代码，不更新 README。

## 设计

新文件使用现有 `apps/web/e2e/helpers.ts`，避免复制导入 bundle、添加 case、追加版本等流程。拆分边界按用户工作域划分：

- `skills-workbench.spec.ts`：工作台基础闭环、导入、权限、治理、候选版本和移动端基础流。
- `run-history-workbench.spec.ts`：历史记录、Run matrix、saved view、run comparison、case version history。

这样失败时可以从文件名直接判断是工作台基础流还是实验历史流，同时保留 Playwright 自动发现 `.spec.ts` 的默认行为。

## 验收

- `apps/web/e2e/skills-workbench.spec.ts` 行数显著下降。
- 新 `apps/web/e2e/run-history-workbench.spec.ts` 行数控制在 300 行左右。
- `cd apps/web && npm run e2e -- skills-workbench.spec.ts run-history-workbench.spec.ts` 通过。
- 完整 API、Web unit、build、typecheck、audit、E2E、diff check 和任务 JSON 检查通过。
