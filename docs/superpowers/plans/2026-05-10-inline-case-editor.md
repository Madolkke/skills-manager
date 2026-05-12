# Inline Case Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户在测评详情面板内直接编辑当前 eval case，并保存为新的 case version。

**Architecture:** 新增 `EvalCaseDetailPanel` 组件承接当前 `EvalPane` 里的详情展示和编辑表单。`DecisionWorkbench` 暴露一个 draft-based `updateCaseDraft`，既给新组件用，也让旧 inspector form 继续复用同一条 PATCH 逻辑。

**Tech Stack:** Next.js App Router、React client components、Playwright E2E、现有 FastAPI API。

---

### Task 1: 红色 E2E

**Files:**
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 新增 inline edit 路径测试**

在 `operator can edit and archive eval cases` 后追加：

```ts
test("operator can edit the selected eval case inline", async ({ page }) => {
  await importSkillBundle(page, `inline-case-editing-${Date.now()}`);
  await addEvalCase(page, "PR: stale inline title");

  await page.locator(".evalCaseDetailPanel").getByRole("button", { name: "编辑" }).click();
  await page.getByLabel("详情内标题").fill("PR: inline edited owner filter");
  await page.getByLabel("详情内 input").fill("diff --git a/service.py b/service.py\\n+return Project.find_many()");
  await page.getByLabel("详情内 expected output").fill("Must flag missing tenant or owner scope.");
  await page.getByLabel("详情内 notes").fill("Inline edit keeps the operator in review context.");
  await page.getByRole("button", { name: "保存为新版本" }).click();

  await expect(page.locator(".caseReviewCard").filter({ hasText: "PR: inline edited owner filter" })).toBeVisible();
  await expect(page.locator(".evalCaseDetailPanel")).toContainText("diff --git a/service.py b/service.py");
  await expect(page.locator(".evalCaseDetailPanel")).toContainText("Must flag missing tenant or owner scope.");
});
```

- [x] **Step 2: 验证红灯**

Run:

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "edit the selected eval case inline"
```

Expected: FAIL，因为 `.evalCaseDetailPanel` 或详情内编辑按钮还不存在。

### Task 2: 组件和数据流

**Files:**
- Create: `apps/web/components/eval-cases/eval-case-detail-panel.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`

- [x] **Step 1: 新建详情组件**

组件 props 接收 `item`、`busy`、`historyVisible`、`history`、`loading`、`onUpdateCase`、`onHistoryCase`、`onArchiveCase`、`onRestoreCaseVersion`。组件内部管理 `editing`，查看态展示内容，编辑态提交 draft。

- [x] **Step 2: 抽出 draft update 函数**

在 `DecisionWorkbench` 中新增 `updateCaseDraft(draft)`，旧 `updateCase(event)` 只负责从 form 读值后调用它。

- [x] **Step 3: 替换 EvalPane 详情区域**

将 `EvalPane` 里 map selected case 的 detail block 替换为 `EvalCaseDetailPanel`，保留 `CaseHistoryPanel` 行为但放入新组件。

### Task 3: 样式和文档

**Files:**
- Modify: `apps/web/app/globals.css`
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Modify: `.agent/tasks/TASK-014.json`

- [x] **Step 1: 样式**

为 `.evalCaseDetailPanel`、`.evalCaseDetailActions`、`.evalCaseInlineForm`、`.evalCaseMetaStrip` 增加紧凑但可读的样式，保持现有工作台视觉语言。

- [x] **Step 2: 文档**

README 试用路径说明 case 可在测评详情面板内编辑；UX review 把 inspector 摩擦项改为部分缓解；完成度审计补充证据。

- [x] **Step 3: 验证并提交**

Run:

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

Expected: 全部通过。然后设置 TASK-014 complete / passes true，提交 `feat: edit eval cases inline`。
