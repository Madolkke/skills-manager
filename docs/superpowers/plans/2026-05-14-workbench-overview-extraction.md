# Workbench Overview Pane 组件抽离计划

## 红灯

- 运行 `test -f apps/web/components/overview/workbench-overview-pane.tsx`，确认目标组件尚不存在。
- 运行 `rg -n "function OverviewPane\\(" apps/web/components/decision-workbench.tsx`，确认旧内联组件仍存在。
- 运行 `wc -l apps/web/components/decision-workbench.tsx`，确认主组件仍过大。

## 实施步骤

1. 新增 `apps/web/components/overview/workbench-overview-pane.tsx`。
2. 将原 OverviewPane 的空态 launchpad、product hero、metrics、设置、权限、治理、验证引导和 bundle preview 迁入新组件。
3. 新增 `apps/web/components/workbench-metric.tsx`，把原本内联的 `Metric` 提成共享组件。
4. 将 `formatBytes` 移入 `apps/web/lib/format.ts`，供概览页和主工作台 diff/import preview 共用。
5. 从 `DecisionWorkbench` 删除内联 `OverviewPane`、bundle preview helper 和局部 `Metric`/`formatBytes`。
6. 在 `DecisionWorkbench` 中用 `WorkbenchOverviewPane` 替换旧调用，保持 props 和 handler 语义不变。
7. 更新 `.agent/tasks.json`、`TASK-032.json` 和执行日志。

## 验证步骤

1. `cd apps/web && npm run typecheck`
2. `cd apps/web && npm run build`
3. `cd apps/api && uv run pytest`
4. `cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e`
5. `git diff --check`

## 回滚策略

如果概览页、bundle preview 或空态 launchpad 回归，恢复 `DecisionWorkbench` 原内联 OverviewPane，删除新组件和本任务文档。由于本任务不修改 API、数据库和 CSS，回滚只影响前端组件结构。
