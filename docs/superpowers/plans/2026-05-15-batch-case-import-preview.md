# 批量 case 导入预览表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在批量粘贴 eval case 时显示逐行导入预览，让用户提交前确认每行状态和解析字段。

**Architecture:** 扩展纯 TS parser 输出 `previewRows`，再用独立 React 组件渲染语义化表格。提交逻辑仍只使用 `valid`，错误阻断仍复用 `ValidatedForm.validate`。

**Tech Stack:** React、Next.js、Vitest、Playwright、CSS。

---

### Task 1: Parser preview rows

**Files:**
- Modify: `apps/web/components/eval-cases/quick-add-cases-parser.ts`
- Modify: `apps/web/components/eval-cases/quick-add-cases-parser.test.ts`

- [x] **Step 1: 写失败测试**
  - 断言 `parseBatchCases` 返回 valid/invalid 混合行的 `previewRows`。

- [x] **Step 2: 跑红灯**
  - Run: `npm run test:unit -- quick-add-cases-parser`
  - Expected: FAIL，当前 parser 没有 `previewRows`。

- [x] **Step 3: 实现 parser preview rows**
  - 每条非空行返回 `lineNumber`、`status`、字段值和错误文案。

### Task 2: Preview table UI

**Files:**
- Create: `apps/web/components/eval-cases/batch-case-preview-table.tsx`
- Modify: `apps/web/components/eval-cases/quick-add-cases.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/e2e/form-errors.spec.ts`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 写 E2E 红测**
  - 有效/无效混合批量粘贴后，断言 `.quickCaseBatchTable` 显示 `可导入` 和 `需修正`。

- [x] **Step 2: 渲染表格**
  - 新组件渲染 caption、行号、状态 chip、标题、Input、Expected output、Notes。
  - 空输入时显示空态，不增加提交路径。

- [x] **Step 3: 样式调整**
  - 表格跨两列，桌面可扫读，移动端横向滚动，不挤压 textarea。

### Task 3: 文档、验证、提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-ux-friction-audit-2026-05-14.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Create: `.agent/tasks/TASK-057.json`

- [x] **Step 1: 更新文档**
  - 写清借鉴来源、预览表边界和后续不做内联编辑。

- [x] **Step 2: 完整验证**
  - `cd apps/api && UV_NO_CACHE=1 uv run pytest`
  - `cd apps/web && npm run test:unit`
  - `cd apps/web && npm run typecheck`
  - `cd apps/web && npm run build`
  - `cd apps/web && npm audit --omit=dev`
  - `cd apps/web && npm run e2e`
  - `git diff --check`
  - `jq empty .agent/tasks.json .agent/tasks/TASK-057.json`
