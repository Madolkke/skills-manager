# Workbench Command 单元测试计划

## 红灯

- 引入 Vitest 最小 runner 和测试脚本。
- 编写 `apps/web/components/command-menu/workbench-command-config.test.ts`。
- 运行 `npm run test:unit -- components/command-menu/workbench-command-config.test.ts`，确认失败原因是缺少 `./workbench-command-config`。

## 实施步骤

1. 使用 `npm install -D vitest` 安装最小单元测试 runner。
2. 新增 `apps/web/vitest.config.ts`，使用 node environment 和 `@` alias。
3. 新增 command config 单元测试，覆盖命令顺序、禁用态、禁用原因和回调派发。
4. 新增 `apps/web/components/command-menu/workbench-command-config.ts`，导出纯 `buildWorkbenchCommands`。
5. 将 `useWorkbenchCommands` 改为 `useMemo` 包装纯 builder。
6. 使用 `npm audit fix` 升级 Next.js 安全补丁，并把 package range 提升到 `^15.5.18`。
7. 更新 README 推送前验证命令。
8. 更新 `.agent/tasks.json`、`TASK-038.json` 和执行日志。

## 验证步骤

1. `cd apps/web && npm run test:unit`
2. `cd apps/web && npm run typecheck`
3. `cd apps/web && npm run build`
4. `cd apps/web && npm audit --omit=dev`
5. `cd apps/api && uv run pytest`
6. `cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e`
7. `git diff --check`

## 回滚策略

如果 Vitest 配置、Next.js 安全补丁或 command builder 抽离造成构建/E2E 回归，恢复 `useWorkbenchCommands` 的直接 command list，移除 Vitest、测试文件和本任务文档。由于本任务不修改后端和 CSS，回滚范围集中在 web 测试配置和 command-menu 模块。
