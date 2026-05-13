# Workbench Command 配置抽离规格

## 背景

`DecisionWorkbench` 的主要 UI pane 已经逐步抽离，但 command menu 的命令配置仍内联在主组件中。命令配置包含导航、创建、测评和证据入口，是用户快速操作路径的集中索引。继续留在主组件里，会让主工作台同时承担业务编排、布局和命令信息架构三类职责。

本任务只做结构性拆分，不改变用户可见行为。

## 用户可见行为

用户打开 command menu 后仍能看到并执行同一组命令：

- 导航：打开概览、变体、测评、历史、审计、差异。
- 创建：导入标准 Skill bundle、新建 skill、新建 variant、追加版本。
- 测评：添加 case、批量添加 case、记录本次测评。
- 证据：比较版本。
- 禁用态：没有持久化 skill 时禁用依赖当前 skill 的命令；默认 variant 少于两个版本时禁用 diff；没有 case 时禁用记录测评。
- 快捷键、命令标题、分组、详情文案和禁用原因保持不变。

## 组件边界

新增 `useWorkbenchCommands`：

- 输入：`hasPersistedSkill`、`casesCount`、`canCompareVersions`、mode 切换回调、Inspector action 回调和 diff 回调。
- 输出：`CommandMenuItem[]`。
- hook 内部负责命令信息架构、禁用态和 command item 构造。
- hook 不直接调用业务 API，不读取 workbench 全量状态，不维护 command menu 打开/关闭状态。

`DecisionWorkbench` 保留：

- 当前 mode、选中 skill、case 列表、默认 variant 和 diff pair 判断。
- `chooseAction`、`openDiffMode` 和 `setMode`。
- `CommandMenu` 的渲染位置和 `scopeLabel`。

## 非目标

- 不重做 CommandMenu 视觉或 ARIA。
- 不新增、删除或重命名命令。
- 不改变快捷键、disabled reason、执行行为或命令排序。
- 不把业务 API mutation 迁入 command-menu 模块。

## 验收标准

- `apps/web/components/command-menu/use-workbench-commands.ts` 存在。
- `DecisionWorkbench` 中不再存在内联 `const commandItems = useMemo` 或 `function command`。
- `DecisionWorkbench` 不再直接依赖 `CommandMenuItem` 类型。
- `DecisionWorkbench` 行数减少，`useWorkbenchCommands` 文件保持在 200 行以内。
- TypeScript、构建、API 测试、E2E 和 `git diff --check` 全部通过。
