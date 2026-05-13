# Workbench Modes Tablist 键盘语义 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把工作区模式切换改成符合 APG Tabs 的键盘模型。

**Architecture:** 新增 `WorkbenchTabs` 组件封装 tablist 语义和方向键导航，`DecisionWorkbench` 只负责声明可见 tabs 和 mode 切换。当前 panel 外层提供 `role=tabpanel`，与 active tab 建立稳定 `aria-labelledby` / `aria-controls` 关系。

**Tech Stack:** React client component、原生 button、WAI-ARIA Tabs Pattern、Playwright E2E。

---

### Task 1: 任务登记和红色 E2E

**Files:**
- Create: `.agent/tasks/TASK-029.json`
- Modify: `.agent/tasks.json`
- Modify: `apps/web/e2e/accessibility-workbench.spec.ts`

- [x] **Step 1: 登记 TASK-029**

在 `.agent/tasks.json` 追加 TASK-029，初始 `passes=false`。

- [x] **Step 2: 写红色 E2E**

在 `apps/web/e2e/accessibility-workbench.spec.ts` 新增：

```ts
test("workbench modes use tablist keyboard navigation", async ({ page }) => {
  await importSkillBundle(page, `tabs-${Date.now()}`);

  const tablist = page.getByRole("tablist", { name: "Workbench modes" });
  const overviewTab = tablist.getByRole("tab", { name: "概览" });
  const variantsTab = tablist.getByRole("tab", { name: "变体" });
  const historyTab = tablist.getByRole("tab", { name: "历史" });

  await expect(overviewTab).toHaveAttribute("aria-selected", "true");
  await expect(overviewTab).toHaveAttribute("tabindex", "0");
  await expect(variantsTab).toHaveAttribute("aria-selected", "false");
  await expect(variantsTab).toHaveAttribute("tabindex", "-1");
  await expect(page.getByRole("tabpanel", { name: "概览" })).toBeVisible();

  await overviewTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(variantsTab).toBeFocused();
  await expect(variantsTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "变体" })).toBeVisible();

  await page.keyboard.press("End");
  await expect(historyTab).toBeFocused();
  await expect(historyTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "历史" })).toBeVisible();

  await page.keyboard.press("Home");
  await expect(overviewTab).toBeFocused();
  await expect(overviewTab).toHaveAttribute("aria-selected", "true");
});
```

- [x] **Step 3: 验证红灯**

运行：

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- accessibility-workbench.spec.ts --grep "workbench modes"
```

预期失败：当前 UI 没有 `role=tablist` / `role=tab` / `role=tabpanel`。

### Task 2: WorkbenchTabs 组件

**Files:**
- Create: `apps/web/components/workbench-tabs.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`

- [x] **Step 1: 新增组件**

创建 `apps/web/components/workbench-tabs.tsx`：

```tsx
"use client";

import { KeyboardEvent } from "react";

export type WorkbenchMode = "overview" | "variants" | "evals" | "diff" | "history" | "audit" | "promotion";

export type WorkbenchTabItem = {
  label: string;
  mode: WorkbenchMode;
  onActivate?: () => void;
};

export function workbenchTabId(mode: WorkbenchMode) {
  return `workbench-tab-${mode}`;
}

export function workbenchPanelId(mode: WorkbenchMode) {
  return `workbench-panel-${mode}`;
}

export function WorkbenchTabs({
  mode,
  onModeChange,
  tabs,
}: {
  mode: WorkbenchMode;
  onModeChange: (mode: WorkbenchMode) => void;
  tabs: WorkbenchTabItem[];
}) {
  function activate(tab: WorkbenchTabItem) {
    if (tab.onActivate) tab.onActivate();
    else onModeChange(tab.mode);
    window.requestAnimationFrame(() => {
      document.getElementById(workbenchTabId(tab.mode))?.focus();
    });
  }

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, targetIndex: number) {
    event.preventDefault();
    const index = (targetIndex + tabs.length) % tabs.length;
    activate(tabs[index]);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === "ArrowRight") moveFocus(event, index + 1);
    if (event.key === "ArrowLeft") moveFocus(event, index - 1);
    if (event.key === "Home") moveFocus(event, 0);
    if (event.key === "End") moveFocus(event, tabs.length - 1);
  }

  return (
    <div aria-label="Workbench modes" className="linearTabs" role="tablist">
      {tabs.map((tab, index) => {
        const isActive = tab.mode === mode;
        return (
          <button
            aria-controls={workbenchPanelId(tab.mode)}
            aria-selected={isActive}
            className={isActive ? "linearTabActive" : ""}
            id={workbenchTabId(tab.mode)}
            key={tab.mode}
            onClick={() => activate(tab)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            role="tab"
            tabIndex={isActive ? 0 : -1}
            type="button"
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [x] **Step 2: 接入 DecisionWorkbench**

在 `decision-workbench.tsx` 中导入：

```ts
import { WorkbenchTabs, type WorkbenchMode, workbenchPanelId, workbenchTabId } from "@/components/workbench-tabs";
```

把 `type Mode = ...` 改为：

```ts
type Mode = WorkbenchMode;
```

在 render 前创建 tabs：

```ts
const workbenchTabs = [
  { label: "概览", mode: "overview" as const },
  { label: "变体", mode: "variants" as const },
  { label: "测评", mode: "evals" as const },
  { label: "差异", mode: "diff" as const, onActivate: () => openDiffMode() },
  { label: "历史", mode: "history" as const },
];
if (mode === "audit") workbenchTabs.push({ label: "审计", mode: "audit" as const });
if (mode === "promotion" || promotionReview) workbenchTabs.push({ label: "评审", mode: "promotion" as const });
```

用 `<WorkbenchTabs mode={mode} onModeChange={setMode} tabs={workbenchTabs} />` 替换原来的 `<nav className="linearTabs">`。

- [x] **Step 3: 增加 tabpanel 外层**

把 mode 内容包进：

```tsx
<section
  aria-labelledby={workbenchTabId(mode)}
  className="workbenchTabPanel"
  id={workbenchPanelId(mode)}
  role="tabpanel"
>
  {/* existing mode panes */}
</section>
```

### Task 3: 文档、验证和提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Modify: `.agent/tasks/TASK-029.json`

- [x] **Step 1: 更新中文文档**

记录 Workbench modes 已按 APG Tabs Pattern 补齐 tablist、tabpanel 和方向键导航；剩余 accessibility 风险仍是人工读屏验收和其他复合组件巡检。

- [x] **Step 2: 完整验证**

运行：

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

- [x] **Step 3: 提交**

设置 TASK-029 complete / passes true，提交：

```bash
git commit -m "fix: improve workbench tab keyboard navigation"
```
