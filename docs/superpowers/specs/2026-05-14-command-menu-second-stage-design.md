# Command menu 第二阶段设计

## 背景

当前 `Cmd/Ctrl+K` 命令菜单已经完成第一阶段：可以搜索执行导入、创建、测评、历史和差异等高频动作，并且会根据当前 workbench mode 排序。问题是它仍然像“静态命令清单”，还没有体现成熟产品里的三个关键能力：

1. 用户刚刚用过的命令应该更容易再次触达。
2. 命令应该理解当前选择，例如当前 case、当前 run。
3. 执行前应该能快速判断命令会作用到什么对象，而不是只看一行标题。

本轮目标是把命令菜单从“全局搜索框”推进到“当前工作台操作层”。它仍然不做 AI 推荐、不做全局资源搜索、不做服务器端个性化，只把用户已表达的上下文变成可验证的 UI 行为。

## 外部实践

- [GitHub Command Palette](https://docs.github.com/en/get-started/accessibility/github-command-palette) 会根据当前 UI 位置决定 scope，并使用当前上下文和最近资源给出建议。SkillHub 适配为：命令仍限定在当前 skill 工作区，最近使用只影响空查询下的本地排序。
- [VS Code Keyboard Shortcuts](https://code.visualstudio.com/docs/configure/keybindings) 强调命令可以带 `when` 上下文条件，快捷键是否生效取决于当前焦点和状态。SkillHub 适配为：当前 case / 当前 run 存在时才出现选择感知命令。
- [Raycast Script Commands](https://manual.raycast.com/script-commands) 把个人工作流转成可搜索的一等命令，并通过 title/description 元数据帮助用户判断动作。SkillHub 适配为：每条命令有 preview，展示命令作用范围、对象和限制。

## 产品设计

### 1. 最近使用

用户执行命令后，把 command id 写入浏览器本地 `localStorage`，保留最近 5 条。再次打开命令菜单且搜索框为空时，最近命令在当前 mode priority 之上排序；但禁用命令仍然下沉。

例子：

- 用户在 `测评` 页执行过 `添加 case`。
- 关闭菜单后再次打开 `Cmd/Ctrl+K`。
- 第一屏会优先显示 `添加 case`，而不是仅按 mode 默认显示 `记录本次测评`。
- 用户输入搜索词时，搜索结果仍以匹配为主，不强行把无关最近命令插入。

### 2. Selection-aware commands

命令菜单只读取已有 selection，不引入新的状态模型。

当前可见选择：

- `selectedCase`：测评页当前 case。
- `selectedRun`：历史页当前 run。

新增命令：

- `查看当前 case 历史`：存在 `selectedCase` 时显示，执行后打开该 case 的历史版本面板。
- `设为对照 run`：存在 `selectedRun` 时显示，执行后把当前 run 填入 comparison baseline。
- `设为候选 run`：存在 `selectedRun` 时显示，执行后把当前 run 填入 comparison candidate。

例子：

- 用户在测评页选中 `PR: missing owner filter`。
- 打开命令菜单，第一屏出现 `查看当前 case 历史`。
- 右侧 preview 显示对象：`PR: missing owner filter`、作用：打开 case version timeline。
- 按 Enter 后仍停留在测评页，但 case history 面板展开并展示该 case 的版本记录。

### 3. Command preview

弹层改为两列：左侧命令列表，右侧 preview。preview 不增加可聚焦控件，避免破坏 `dialog + combobox + listbox` 的键盘模型。

preview 展示：

- 命令标题。
- 命令说明或禁用原因。
- 结构化 facts，例如 `Scope`、`对象`、`快捷键`。

例子：

- 高亮 `记录本次测评`：preview 显示当前测试用例数量、作用对象是当前 variant version。
- 高亮 `查看当前 case 历史`：preview 显示当前 case 标题和 case id。
- 高亮被禁用的 `比较版本`：preview 显示禁用原因“当前 variant 至少需要两个版本”。

## 范围

本轮修改：

- `apps/web/components/command-menu/command-menu-types.ts`
- `apps/web/components/command-menu/command-menu-recents.ts`
- `apps/web/components/command-menu/command-menu-preview.tsx`
- `apps/web/components/command-menu/command-menu.tsx`
- `apps/web/components/command-menu/workbench-command-config.ts`
- `apps/web/components/command-menu/use-workbench-commands.ts`
- `apps/web/components/decision-workbench.tsx`
- `apps/web/components/command-menu/*.test.ts`
- `apps/web/e2e/skills-workbench.spec.ts`

本轮不做：

- 服务器端个性化或跨设备同步。
- AI 推荐、模糊语义排序、跨 skill 全局搜索。
- 快捷键自定义。
- 命令菜单整体视觉重做。

## 验收标准

- Vitest 覆盖最近命令去重、限长、排序和禁用命令下沉。
- Vitest 覆盖 selection-aware 命令：选中 case 时可打开 case history；选中 run 时可设为 baseline/candidate。
- E2E 覆盖用户执行 `添加 case` 后再次打开菜单，最近命令排在第一屏。
- E2E 覆盖用户选中 case 后从命令菜单打开 case history，并能看到 preview。
- 现有命令菜单 ARIA、Tab trap、搜索执行、mode-aware priority 和完整 SkillHub E2E 不回归。
- README、产品体验评审、摩擦审计、完成度审计、任务日志同步更新。
