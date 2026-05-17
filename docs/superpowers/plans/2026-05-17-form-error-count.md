# Form Error Count Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `ValidatedForm` 的错误摘要直接显示需要修正的字段数量，提升复杂表单的错误恢复速度。

**Architecture:** 只改共享 `FormErrorSummary` 渲染文案，不新增状态或每个表单的特殊逻辑。用现有 Launchpad required-fields E2E 做红绿测试，确保数量提示、summary 聚焦和链接回字段同时成立。

**Tech Stack:** React、Next.js、Playwright、Vitest。

---

### Task 1: Error count summary

**Files:**
- Modify: `apps/web/components/forms/form-validation.tsx`
- Modify: `apps/web/e2e/form-errors.spec.ts`

- [x] **Step 1: 写 E2E 红测**
  - 更新 `launchpad required fields show an error summary and focus recovery links`。
  - 提交空白新建 skill 后，断言 `.skillLaunchpadForm .formErrorSummary` 包含 `6 个字段需要修正。修正后再提交。`。
  - 保留原断言：summary 可见、聚焦、包含 `填写 Skill ID`、`slug` 字段 `aria-invalid=true`、点击摘要链接后聚焦 `slug`。

- [x] **Step 2: 跑 E2E 红灯**
  - Run: `cd apps/web && npm run e2e -- form-errors.spec.ts -g "launchpad required fields"`
  - Expected: FAIL，因为当前 summary 只显示 `修正后再提交。`。

- [x] **Step 3: 实现错误数量文案**
  - 在 `FormErrorSummary` 中把说明段落改为：
    - `<p>{errors.length} 个字段需要修正。修正后再提交。</p>`
  - 不改变 `role`、`tabIndex`、link 和 field focus 逻辑。

- [x] **Step 4: 跑 E2E 绿灯**
  - Run: `cd apps/web && npm run e2e -- form-errors.spec.ts -g "launchpad required fields"`
  - Expected: PASS。

### Task 2: 文档、完整验证、提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-ux-friction-audit-2026-05-14.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Create: `.agent/tasks/TASK-066.json`

- [x] **Step 1: 更新中文文档和任务记录**
  - 记录错误摘要现在会显示需要修正的字段数量。
  - 记录这只是错误恢复可见性增强，不是新的校验规则。

- [x] **Step 2: 完整验证**
  - `cd apps/api && UV_NO_CACHE=1 uv run pytest`
  - `cd apps/web && npm run test:unit`
  - `cd apps/web && npm run typecheck`
  - `cd apps/web && npm run build`
  - `cd apps/web && npm audit --omit=dev`
  - `cd apps/web && npm run e2e`
  - `git diff --check`
  - `jq empty .agent/tasks.json .agent/tasks/TASK-066.json`
