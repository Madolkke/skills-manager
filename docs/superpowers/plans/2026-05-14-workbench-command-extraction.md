# Workbench Command 配置抽离计划

## 红灯

- 运行 `test -f apps/web/components/command-menu/use-workbench-commands.ts`，确认目标 hook 尚不存在。
- 运行 `rg -n "const commandItems = useMemo|function command\\(" apps/web/components/decision-workbench.tsx`，确认旧内联命令配置仍存在。
- 运行 `wc -l apps/web/components/decision-workbench.tsx`，确认主组件仍过大。

## 实施步骤

1. 新增 `apps/web/components/command-menu/use-workbench-commands.ts`。
2. 将原 command list 和 command factory 迁入 hook。
3. 让 hook 只接收必要状态和回调：`hasPersistedSkill`、`casesCount`、`canCompareVersions`、`onSetMode`、`onAction`、`onOpenDiff`。
4. 从 `DecisionWorkbench` 删除内联 `commandItems` useMemo、`command()` factory 和 `CommandMenuItem` import。
5. 在 `DecisionWorkbench` 中调用 `useWorkbenchCommands`，保持 `CommandMenu` 渲染位置不变。
6. 更新 `.agent/tasks.json`、`TASK-037.json` 和执行日志。

## 验证步骤

1. `cd apps/web && npm run typecheck`
2. `cd apps/web && npm run build`
3. `cd apps/api && uv run pytest`
4. `cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e`
5. `git diff --check`

## 回滚策略

如果 command menu 的命令、禁用态、快捷键或执行行为回归，恢复 `DecisionWorkbench` 原内联 command 配置，删除新 hook 和本任务文档。由于本任务不修改 API、数据库和 CSS，回滚只影响前端命令配置结构。
