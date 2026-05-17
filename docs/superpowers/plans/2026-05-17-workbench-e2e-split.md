# Workbench E2E Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将工作台历史实验相关 Playwright 测试从超大的 `skills-workbench.spec.ts` 拆到独立文件，保持行为验证不变。

**Architecture:** 只移动测试代码，不改生产代码。新文件复用 `apps/web/e2e/helpers.ts` 的公开 helper，按“实验历史工作域”承载 history、Run matrix、saved view、comparison 和 case version history。

**Tech Stack:** Playwright、TypeScript、现有 E2E helpers、中文任务记录。

---

### Task 1: 建立任务记录和拆分目标

**Files:**
- Create: `.agent/tasks/TASK-076.json`
- Modify: `.agent/tasks.json`
- Create: `docs/superpowers/specs/2026-05-17-workbench-e2e-split-design.md`
- Create: `docs/superpowers/plans/2026-05-17-workbench-e2e-split.md`

- [ ] **Step 1: 记录任务范围**

写入 TASK-076，明确只拆测试规格文件，不改用户行为、不改生产代码。

- [ ] **Step 2: 把任务追加到 manifest**

在 `.agent/tasks.json` 追加 `id: "076"`，初始 `passes: false`。

### Task 2: 拆出历史实验规格文件

**Files:**
- Create: `apps/web/e2e/run-history-workbench.spec.ts`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [ ] **Step 1: 从原文件移动测试**

把以下测试完整移动到新文件，测试标题和断言保持不变：

```text
operator can review eval run history with filters
operator can inspect run matrix across eval runs
operator can save and reapply an eval run history view
operator can compare eval runs and accept a verification pointer
operator can inspect eval case version history
operator can restore an older eval case version
```

- [ ] **Step 2: 修正 imports**

`run-history-workbench.spec.ts` 导入：

```ts
import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { addEvalCase, appendSkillBundleVersion, importSkillBundle } from "./helpers";
```

`skills-workbench.spec.ts` 删除不再使用的 `readFile` import，保留移动端测试仍需要的 `reloadWorkbench`。

### Task 3: 验证拆分没有改变覆盖面

**Files:**
- Modify: `.agent/tasks/TASK-076.json`
- Modify: `.agent/logs/LOG.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`

- [ ] **Step 1: 定点 E2E**

Run:

```bash
cd apps/web && npm run e2e -- skills-workbench.spec.ts run-history-workbench.spec.ts
```

Expected: 两个规格文件全部通过，测试数量等于拆分前相关测试总量。

- [ ] **Step 2: 完整验证**

Run:

```bash
cd apps/api && UV_NO_CACHE=1 uv run pytest
cd apps/web && npm run test:unit
cd apps/web && npm run build
cd apps/web && npm audit --omit=dev
cd apps/web && npm run typecheck
cd apps/web && npm run e2e
git diff --check
jq empty .agent/tasks.json .agent/tasks/TASK-076.json
```

Expected: 全部通过，完整 Playwright 测试数量不减少。

- [ ] **Step 3: 更新任务状态并提交**

TASK-076 `status` 改为 `complete`，`.agent/tasks.json` 中 `passes` 改为 `true`，提交信息：

```bash
git commit -m "test: split workbench run history e2e specs"
```
