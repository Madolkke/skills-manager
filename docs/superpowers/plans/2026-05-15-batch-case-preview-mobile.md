# 批量 case 预览移动端护栏 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for behavior change and superpowers:verification-before-completion before claiming completion.

**Goal:** 确保批量 case 导入预览在移动端纵向排布，不把 textarea 和统计卡挤成难读的两栏。

**Architecture:** 用 Playwright mobile viewport 保护真实工作流；CSS 只新增 quick case 区域的窄屏布局，不改数据流。

**Tech Stack:** React、Next.js、Playwright、CSS。

---

### Task 1: 移动端红绿测试

**Files:**
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 写移动端 E2E**
  - 导入标准 Skill bundle 后切换到 390px viewport。
  - 批量粘贴两行 case，断言统计卡在 textarea 下方。
  - 断言页面没有横向文档滚动，预览表只在内部滚动。

- [x] **Step 2: 跑红灯**
  - Run: `npm run e2e -- skills-workbench.spec.ts -g "batch case preview stacks"`
  - Expected: FAIL，统计卡仍在 textarea 同行。

### Task 2: CSS 响应式护栏

**Files:**
- Modify: `apps/web/app/globals.css`

- [x] **Step 1: 新增窄屏 quick case 样式**
  - `quickCaseHeader` 纵向排布。
  - `quickCaseGrid` 和 `quickCaseBatch` 改为单列。
  - 统计卡、提交按钮和表格容器填满可用宽度。

- [x] **Step 2: 跑目标绿灯**
  - Run: `npm run e2e -- skills-workbench.spec.ts -g "batch case preview stacks"`
  - Expected: PASS。

### Task 3: 文档、验证、提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-ux-friction-audit-2026-05-14.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Create: `.agent/tasks/TASK-058.json`

- [x] **Step 1: 更新中文文档**
  - 记录移动端批量预览的布局边界和验证方式。

- [x] **Step 2: 完整验证**
  - `cd apps/api && UV_NO_CACHE=1 uv run pytest`
  - `cd apps/web && npm run test:unit`
  - `cd apps/web && npm run typecheck`
  - `cd apps/web && npm run build`
  - `cd apps/web && npm audit --omit=dev`
  - `cd apps/web && npm run e2e`
  - `git diff --check`
  - `jq empty .agent/tasks.json .agent/tasks/TASK-058.json`
