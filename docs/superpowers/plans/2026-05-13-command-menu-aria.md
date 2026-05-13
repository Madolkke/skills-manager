# Command Menu ARIA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 SkillHub command menu 升级成可测试的 dialog + editable combobox + listbox 模式。

**Architecture:** 保留现有 `CommandMenu` 组件和视觉结构，补齐 ARIA 属性、稳定 id、关闭按钮、Tab trap 和回焦点。用 Playwright E2E 锁定真实键盘和 DOM 语义，不引入外部依赖。

**Tech Stack:** React `useId` / refs、Next.js client component、WAI-ARIA combobox/listbox/dialog semantics、Playwright E2E。

---

### Task 1: 任务登记和红色 E2E

**Files:**
- Create: `.agent/tasks/TASK-026.json`
- Modify: `.agent/tasks.json`
- Modify: `apps/web/e2e/accessibility-workbench.spec.ts`

- [x] **Step 1: 登记 TASK-026**

在 `.agent/tasks.json` 追加：

```json
{
  "id": "026",
  "title": "补齐 Command Menu ARIA 语义",
  "priority": 26,
  "passes": false,
  "spec": ".agent/tasks/TASK-026.json"
}
```

- [x] **Step 2: 写红色 E2E**

在 `apps/web/e2e/accessibility-workbench.spec.ts` 新增测试：

- 打开 command menu 后搜索框是 `role=combobox`，有 `aria-controls` 和 `aria-activedescendant`。
- `ArrowDown` 后 `aria-activedescendant` 更新，并指向 listbox 内的 option。
- `Tab` 在 combobox 和关闭按钮之间循环，不跑到背景页面。
- 关闭菜单后焦点回到打开菜单的按钮。

- [x] **Step 3: 验证红灯**

运行：

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- accessibility-workbench.spec.ts --grep "command menu"
```

预期失败，因为当前 input 不是 combobox，也没有关闭按钮。

### Task 2: CommandMenu ARIA 和焦点管理

**Files:**
- Modify: `apps/web/components/command-menu/command-menu.tsx`

- [x] **Step 1: 增加稳定 id 和 opener ref**

使用 `useId` 生成 menu id，派生 `titleId`、`inputId`、`listboxId` 和 option id；打开菜单时保存当前 active element。

- [x] **Step 2: 新增 closeCommandMenu**

集中关闭逻辑：关闭、清空 query、activeIndex 归零，并在下一帧把焦点恢复到 opener。

- [x] **Step 3: 给 input/listbox/option 补 ARIA**

input 设置 `role=combobox`、`aria-autocomplete=list`、`aria-expanded`、`aria-controls`、`aria-activedescendant`；listbox 设置 id；option 设置 id、`aria-selected`、`aria-disabled` 和 `tabIndex=-1`。

- [x] **Step 4: 增加关闭按钮和 Tab trap**

新增 `关闭命令菜单` button，Tab 在 input 和 close button 之间循环，Escape 关闭并回焦点。

### Task 3: 样式和文档

**Files:**
- Modify: `apps/web/app/globals.css`
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Modify: `.agent/tasks/TASK-026.json`

- [x] **Step 1: 样式**

新增 `.commandMenuClose` 样式，并把 disabled option 样式从 `:disabled` 改为 `[aria-disabled="true"]`。

- [x] **Step 2: 中文文档**

记录 command menu 已补齐 ARIA combobox/listbox/dialog 语义，仍未覆盖 run matrix 表格语义。

- [x] **Step 3: 完整验证**

运行：

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

- [x] **Step 4: 提交**

设置 TASK-026 complete / passes true，提交：

```bash
git commit -m "fix: improve command menu accessibility"
```
