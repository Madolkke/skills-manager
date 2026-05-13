# Command Menu ARIA 语义设计

日期：2026-05-13

## 背景

SkillHub 的 `Cmd/Ctrl+K` 已经能搜索并执行命令，但它的可访问性还停在“可用”层面：输入框不是 combobox，active item 只靠视觉 class，listbox 关系没有通过 `aria-activedescendant` 暴露，modal dialog 也没有显式关闭按钮和 Tab 循环。作为成熟产品里的高频入口，command menu 不能只是鼠标和视觉用户顺手，也要让键盘和读屏用户理解“当前命令、可用结果、如何关闭”。

## 外部实践

- WAI-ARIA APG Combobox Pattern 要求 editable combobox 在弹出 listbox 时保持 DOM focus 在输入框上，并用 `aria-activedescendant` 指向当前 active option；`Enter` 接受当前 option，`Escape` 关闭 popup，方向键移动 option。适配到 SkillHub：搜索框使用 `role=combobox`，listbox option 用稳定 id，方向键只更新 `aria-activedescendant` 和视觉 active 状态。来源：<https://www.w3.org/WAI/ARIA/apg/patterns/combobox/>
- WAI-ARIA APG Modal Dialog Pattern 要求 modal 打开时 focus 进入 dialog，`Tab` / `Shift+Tab` 不离开 dialog，`Escape` 关闭，并建议包含可见关闭按钮。适配到 SkillHub：command menu 增加关闭按钮，Tab 在搜索框和关闭按钮之间循环，关闭后焦点回到触发按钮。来源：<https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/>
- WAI-ARIA APG Keyboard Interface 指出复合组件可用 `aria-activedescendant` 在 DOM focus 留在容器时向辅助技术报告 active descendant。适配到 SkillHub：不让 option 进入 Tab 序列，避免用户在几十条命令之间 Tab。来源：<https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/>
- Vercel Web Interface Guidelines 强调 icon-only button 需要 `aria-label`、语义 HTML 优先、interactive 元素要能键盘操作、focus visible 不可丢失。适配到 SkillHub：关闭按钮给明确 `aria-label`，command options 仍由输入框键盘控制，并保留可见 active/focus 状态。来源：<https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md>

## 方案

采用“dialog + editable combobox + listbox popup”的命令菜单：

1. `CommandMenu` 保持 `role=dialog` 和 `aria-modal=true`，新增 `aria-labelledby` 指向稳定的可见标题 `Command menu`，scope 作为辅助上下文展示。
2. 搜索 input 增加 `role=combobox`、`aria-autocomplete=list`、`aria-expanded=true`、`aria-controls=<listbox id>`、`aria-activedescendant=<active option id>`。
3. listbox 增加稳定 id；每个 option 有稳定 id、`role=option`、`aria-selected`、`aria-disabled`。option 不进入 Tab 序列，DOM focus 始终留在 input 或关闭按钮。
4. 新增可见关闭按钮 `关闭命令菜单`。`Escape` 和关闭按钮都会关闭 dialog，并把焦点恢复到打开菜单前的元素。
5. Tab trap 只在 command dialog 内循环：input -> close button -> input；Shift+Tab 反向循环。
6. 保持现有视觉，不做新布局，只补 `.commandMenuClose` 和 disabled option 的样式。

## 非目标

- 不把 command menu 做成完整路由搜索或多选选择器。
- 不引入外部组件库。
- 不实现 typeahead 以外的复杂组合键，例如 PageUp/PageDown。
- 不在本轮改 run matrix ARIA。

## 验收

- 新增 E2E 先红后绿，覆盖 combobox/listbox 属性、ArrowDown 更新 `aria-activedescendant`、Tab trap、关闭后回焦点。
- 现有 command menu E2E 继续通过。
- 完整验证通过：API pytest、web typecheck、web build、web E2E、`git diff --check`。
