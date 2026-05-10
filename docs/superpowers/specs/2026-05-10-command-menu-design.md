# SkillHub 上下文命令菜单设计

日期：2026-05-10

## 背景

当前 `/skills` 工作台已经有完整证据链，但高频操作仍主要靠右侧 inspector 和多个 tab。`decision-workbench.tsx` 已超过 2200 行，继续把按钮和条件分支塞进去会让后续功能变慢。

本轮目标不是做完整自动化，而是补一个成熟产品常见的操作层：上下文命令菜单。

## 调研结论

- Linear 的动作模型强调同一动作可以通过按钮、快捷键、上下文菜单、命令菜单触发，命令菜单会根据当前 view 或 selection 优先展示相关命令。参考：<https://linear.app/docs/conceptual-model>
- GitHub Command Palette 支持从键盘打开、导航、搜索、运行命令，并把 scope 绑定到当前上下文。参考：<https://docs.github.com/get-started/using-github/github-command-palette>
- SkillHub 适合借鉴这两个点：保留可发现的按钮，同时让熟练用户能通过 `Cmd/Ctrl+K` 快速进入创建、测评、历史、差异和验证流程。

## 产品设计

命令菜单是一个覆盖层，而不是新页面。

打开方式：

- 顶部 `Cmd K` 按钮。
- macOS `Meta+K`，Windows/Linux `Ctrl+K`。
- `Esc` 关闭。

第一版命令：

- 导航：打开概览、变体、测评、差异、历史。
- 创建：导入标准 Skill bundle、新建 skill、新建 variant、追加版本、添加 case。
- 测评：记录本次测评。
- 证据：比较版本、查看 run history。

命令应该显示：

- 命令标题。
- 分组。
- 简短说明。
- 不可用状态和原因，例如没有 skill 时不能新增 variant。

## 技术设计

- 新增 `apps/web/components/command-menu/command-menu.tsx`，只负责交互、过滤、键盘控制和渲染。
- 新增 `apps/web/components/command-menu/global-command-button.tsx`，让 `AppShell` 的顶部按钮通过 DOM event 打开当前页面的命令菜单。
- `DecisionWorkbench` 只负责提供当前上下文下可用的命令数组，不把命令菜单 UI 写回大组件。
- 命令执行复用现有 `chooseAction`、`setMode`、`openDiffMode`，不新增后端。

## 验收标准

1. `Cmd/Ctrl+K` 可以打开命令菜单。
2. 顶部 `Cmd K` 按钮可以打开命令菜单。
3. 搜索 `添加 case` 后回车，可以进入添加测试用例表单。
4. 没有 skill 时，依赖当前 skill 的命令显示禁用，不会执行。
5. Playwright 覆盖主路径。
6. `npm run typecheck`、`npm run build`、`npm run e2e` 通过。

## 非目标

- 不做跨页面全局搜索。
- 不做命令历史、最近命令、用户自定义快捷键。
- 不做批量操作。
- 不引入第三方 command palette 依赖。
