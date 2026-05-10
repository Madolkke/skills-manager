# Run Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让历史页展示多次 eval run 在每个 case 上的 pass/fail 矩阵。

**Architecture:** 后端新增 `eval_run_matrix_for_skill` read model，复用现有 run filters，并按 `case_id` 聚合 exact case version results。前端新增独立 `RunMatrixPanel`，由 `DecisionWorkbench` 与历史页 filters 同步加载。

**Tech Stack:** FastAPI、SQLAlchemy repository、Next.js React client components、TypeScript、Playwright E2E。

---

### Task 1: 红测和任务定义

**Files:**
- Add: `.agent/tasks/TASK-011.json`
- Modify: `.agent/tasks.json`
- Modify: `apps/api/tests/test_sql_repository.py`
- Modify: `apps/api/tests/test_api_commands.py`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 添加 TASK-011 定义**

记录 run matrix 的范围、非目标和验证命令。

- [x] **Step 2: 写 repository 红测**

新增 `test_eval_run_matrix_returns_case_rows_and_run_columns`：创建两条 case，记录 baseline run 一过一不过，追加 candidate version 后记录 candidate run 全过。断言：

```python
matrix = self.repository.eval_run_matrix_for_skill(skill_id=skill.skill_id)
self.assertEqual([row["case"]["title"] for row in matrix["cases"]], ["PR: missing tenant scope", "PR: token logging"])
self.assertEqual(len(matrix["runs"]), 2)
self.assertEqual(len(matrix["cells"]), 4)
```

- [x] **Step 3: 写 API 红测**

新增 `test_eval_run_matrix_endpoint_respects_variant_filter`：调用 `/api/skills/{skill_id}/eval-run-matrix`，再用 `variant_version_id` 过滤，断言过滤后只返回 candidate run 和对应 cells。

- [x] **Step 4: 写 E2E 红测**

新增 `operator can inspect run matrix across eval runs`：导入 skill，批量添加两条 case，记录 baseline run；追加 candidate 后记录 candidate run；打开 `历史`，断言 `Run matrix`、两个 case 行、两个 run column 和 pass/fail cell 可见。

### Task 2: 后端 read model

**Files:**
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`
- Modify: `apps/api/skillhub/api/main.py`

- [x] **Step 1: 新增 repository method**

新增 `eval_run_matrix_for_skill(...)`，查询 run rows 后收集每个 run 的 case results、case version、case title，并返回 `skill/runs/cases/cells`。

- [x] **Step 2: 新增 FastAPI route**

新增 `GET /api/skills/{skill_id}/eval-run-matrix`，query 参数与 history route 一致。

- [x] **Step 3: 跑后端目标测试**

```bash
cd apps/api && uv run pytest tests/test_sql_repository.py::SqlSkillRepositoryTest::test_eval_run_matrix_returns_case_rows_and_run_columns tests/test_api_commands.py::ApiCommandTest::test_eval_run_matrix_endpoint_respects_variant_filter
```

预期：通过。

### Task 3: 前端矩阵面板

**Files:**
- Modify: `apps/web/lib/types.ts`
- Add: `apps/web/components/run-matrix/run-matrix-panel.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`

- [x] **Step 1: 新增 TypeScript 类型**

新增 `EvalRunMatrix`、`EvalRunMatrixCase`、`EvalRunMatrixCell` 类型。

- [x] **Step 2: 新增 RunMatrixPanel**

组件接收 `matrix` 和 `loading`，渲染固定左侧 case 列和横向滚动 run columns。

- [x] **Step 3: 接入 DecisionWorkbench**

新增 `runMatrix` state，加载 history 时同步加载 matrix，filter 改变时一起刷新。

- [x] **Step 4: 添加样式**

新增 `.runMatrixPanel`、`.runMatrixScroller`、`.runMatrixCellPass`、`.runMatrixCellFail`、`.runMatrixCellMissing` 等样式。

- [x] **Step 5: 跑前端目标测试**

```bash
cd apps/web && npm run typecheck
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "run matrix"
```

预期：通过。

### Task 4: 文档、验证、提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`

- [x] **Step 1: 更新文档**

README 补充 history run matrix；UX review 把 run matrix 从缺口改为已完成垂直切片；完成度审计更新证据和剩余风险。

- [x] **Step 2: 全量验证**

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

- [x] **Step 3: 提交推送**

```bash
git add .
git commit -m "feat: add eval run matrix"
git push
```
