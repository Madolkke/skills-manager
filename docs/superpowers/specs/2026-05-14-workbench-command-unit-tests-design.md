# Workbench Command 单元测试规格

## 背景

`useWorkbenchCommands` 已经把 command menu 配置从 `DecisionWorkbench` 抽离出来，但它仍然缺少更快的单元级护栏。当前所有前端回归主要依赖 Playwright E2E，能覆盖真实用户路径，但对 command id、顺序、快捷键和 disabled reason 这类配置回归反馈太慢。

本任务引入最小 Vitest，只测试纯 command builder，不引入 jsdom 或 React Testing Library。

## 用户可见行为

用户可见行为保持不变：

- command menu 的命令数量、顺序、标题、分组、详情文案和快捷键不变。
- 没有持久化 skill 时，依赖当前 skill 的命令继续禁用并显示同一禁用原因。
- 当前测试集没有 case 时，`记录本次测评` 继续显示 `当前测试集还没有 case。`。
- 默认 variant 少于两个版本时，diff 相关命令继续禁用。
- 命令执行仍然调度同一组 mode/action/diff 回调。

## 技术方案

新增纯函数 `buildWorkbenchCommands`：

- 输入与 `useWorkbenchCommands` 相同：`hasPersistedSkill`、`casesCount`、`canCompareVersions`、`onSetMode`、`onAction`、`onOpenDiff`。
- 输出 `CommandMenuItem[]`。
- 不使用 React hook，因此可在 node 环境用 Vitest 直接测试。

`useWorkbenchCommands` 保留：

- 只负责 `useMemo` 缓存。
- 调用 `buildWorkbenchCommands`。
- 不保留 command factory 或 command list。

测试覆盖：

- 命令数量、id 顺序、关键 label/group/shortcut。
- 空 skill/无 case/不可 diff 的禁用态和禁用原因。
- 关键命令回调派发：导航、添加 case、比较版本。

## 非目标

- 不引入 jsdom、React Testing Library 或组件测试。
- 不改变 CommandMenu 视觉、ARIA、过滤和键盘交互。
- 不新增或删除命令。
- 不把 E2E 验证替换成单元测试。

## 验收标准

- `apps/web/package.json` 暴露 `npm run test:unit`。
- `apps/web/vitest.config.ts` 存在，使用 node environment。
- `apps/web/components/command-menu/workbench-command-config.test.ts` 存在并通过。
- `npm audit --omit=dev` 无生产依赖漏洞。
- README 的推送前验证命令包含 `npm run test:unit` 和 `npm audit --omit=dev`。
- TypeScript、构建、API 测试、E2E 和 `git diff --check` 全部通过。
