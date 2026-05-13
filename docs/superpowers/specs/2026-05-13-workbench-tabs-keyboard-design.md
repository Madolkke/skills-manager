# Workbench Modes Tablist 键盘语义设计

日期：2026-05-13

## 背景

SkillHub 的三栏工作台已经有 command menu、skip link、focus ring、Run matrix 表格语义和 Inspector action focus handoff。但中间工作区的 `概览 / 变体 / 测评 / 差异 / 历史` 仍是一组普通按钮。键盘用户连续 Tab 时会逐个经过这些模式按钮，成本高，也没有向读屏软件表达“这是一个 tabbed workspace”。

## 外部实践

- WCAG 2.4.3 Focus Order 要求顺序导航保留意义和可操作性；SkillHub 应避免让键盘用户在模式切换这种同组控制里走过多重复 tab stop。来源：<https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html>
- WAI-ARIA APG Keyboard Interface 建议 `Tab` 在组件之间移动，方向键在复合组件内部移动；tablist 这种复合组件只应把当前项纳入 Tab 顺序。来源：<https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/>
- WAI-ARIA APG Tabs Pattern 要求容器使用 `role=tablist`，每个 tab 使用 `role=tab`、`aria-selected` 和 `aria-controls`，内容区使用 `role=tabpanel`；水平 tablist 支持 Left/Right/Home/End。来源：<https://www.w3.org/WAI/ARIA/apg/patterns/tabs/>
- Vercel Web Interface Guidelines 强调键盘可操作、清晰 focus、准确 accessible name 和“semantics before ARIA”。适配到 SkillHub：继续使用原生 `button`，只补 tab pattern 必需语义和键盘行为。来源：<https://vercel.com/design/guidelines>
- Linear 的交互理念是同一个 action 可以通过按钮、快捷键、上下文菜单和命令菜单访问。适配到 SkillHub：mode tabs、command menu 和页面按钮都保留同一套目标，不制造第二种状态模型。来源：<https://linear.app/docs/conceptual-model>

## 方案

1. 抽出 `WorkbenchTabs` 小组件，避免继续膨胀 `decision-workbench.tsx`。
2. `WorkbenchTabs` 接收当前 mode、tabs 列表和 `onModeChange`。每个 tab 是原生 `button`，同时带 `role=tab`、`aria-selected`、`aria-controls` 和 roving `tabIndex`。
3. 方向键行为：
   - `ArrowRight` 移到下一个 tab，末尾回到第一个。
   - `ArrowLeft` 移到上一个 tab，开头回到最后一个。
   - `Home` 移到第一个。
   - `End` 移到最后一个。
   - 移动后立即激活对应 mode，因为各 panel 已预加载所需数据或有 loading 态，不会造成明显等待。
4. 主工作区内容外层增加 `role=tabpanel`，用 `aria-labelledby` 指回当前 tab。
5. `差异` tab 继续调用 `openDiffMode()`，保留既有 diff pair 预加载逻辑；其他 tab 调 `setMode(mode)`。

## 非目标

- 不做全站读屏人工验收。
- 不把 catalog、case queue、variant map 全部改成复合组件。
- 不做 URL 深链 tabs；这属于后续导航架构优化。
- 不调整视觉样式，避免把语义任务扩大成视觉重做。

## 验收

- 新增 E2E 先红后绿，证明旧按钮组没有 tablist 语义。
- E2E 覆盖 `role=tablist`、`role=tab`、`aria-selected`、`tabIndex`、`aria-controls`、`role=tabpanel`。
- E2E 覆盖 `ArrowRight`、`End`、`Home` 的键盘切换。
- 完整验证通过：API pytest、web typecheck、web build、web E2E、`git diff --check`。
