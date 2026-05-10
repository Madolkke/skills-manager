# Run Matrix Impact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 History 页 run matrix 中显示所选对照 run 和候选 run 的逐 case impact。

**Architecture:** 不新增后端模型，直接复用现有 `EvalRunMatrix.cells`。`DecisionWorkbench` 把 `compareBaselineRunId` 和 `compareCandidateRunId` 传给 `RunMatrixPanel`，组件内计算并渲染 `Impact` 列。

**Tech Stack:** Next.js React、TypeScript、Playwright。

---

### Task 1: E2E 红灯

**Files:**
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [ ] 在 `operator can inspect run matrix across eval runs` 中选择失败 run 为对照、通过 run 为候选。
- [ ] 断言 `.runMatrixImpactFixed` 出现一次，`.runMatrixImpactStablePass` 出现一次。
- [ ] 运行 `cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "inspect run matrix"`，预期失败，因为 impact UI 尚不存在。

### Task 2: RunMatrixPanel impact UI

**Files:**
- Modify: `apps/web/components/run-matrix/run-matrix-panel.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`

- [ ] `RunMatrixPanel` props 增加 `baselineRunId` 和 `candidateRunId`。
- [ ] 根据 `${run_id}:${case_id}` cells map 计算每个 case 的 impact。
- [ ] 在 case 列后新增 sticky-friendly `Impact` 列，显示 `修复`、`回退`、`稳定通过`、`仍未通过`、`缺失` 或 `选择对照/候选`。
- [ ] 添加对应 CSS 类，颜色与现有 pass/fail chip 体系一致。
- [ ] 运行精准 E2E，预期通过。

### Task 3: 文档和验证

**Files:**
- Modify: `README.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `docs/product-ux-review.md`
- Modify: `.agent/tasks.json`
- Create: `.agent/tasks/TASK-013.json`
- Modify: `.agent/logs/LOG.md`
- Modify: `apps/web/e2e/visual-workbench.spec.ts-snapshots/run-comparison-ready-chromium-darwin.png`

- [ ] 更新中文 README、完成度审计和 UX 复盘。
- [ ] 更新视觉快照。
- [ ] 运行 `cd apps/api && uv run pytest`。
- [ ] 运行 `cd apps/web && npm run typecheck`。
- [ ] 运行 `cd apps/web && npm run build`。
- [ ] 运行 `cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e`。
- [ ] 运行 `git diff --check`。
- [ ] 提交并推送。

