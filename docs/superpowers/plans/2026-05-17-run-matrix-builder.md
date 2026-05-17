# Run Matrix Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Run matrix read model 的 cases/cells 组装规则从 SQL repository 抽到独立应用层 builder。

**Architecture:** Repository 继续做数据库查询并把 rows 转成 dict；`skillhub.application.run_matrix` 提供纯函数，根据 run context、eval set cases 和 case results 生成现有 API shape。

**Tech Stack:** Python 3.12、pytest、SQLAlchemy repository、现有 Run matrix API/E2E。

---

### Task 1: 建立任务记录

**Files:**
- Create: `.agent/tasks/TASK-078.json`
- Modify: `.agent/tasks.json`
- Create: `docs/superpowers/specs/2026-05-17-run-matrix-builder-design.md`
- Create: `docs/superpowers/plans/2026-05-17-run-matrix-builder.md`

- [ ] **Step 1: 记录任务范围**

TASK-078 说明只抽 Run matrix builder，不改 API shape、不改前端行为。

### Task 2: 写红灯测试

**Files:**
- Create: `apps/api/tests/test_run_matrix.py`

- [ ] **Step 1: 添加 builder 契约测试**

测试应导入尚未存在的 `build_eval_run_matrix`，用合成数据覆盖：

```python
matrix = build_eval_run_matrix(
    skill={"id": "skill_1"},
    runs=[{"eval_run": {"id": "run-a"}}, {"eval_run": {"id": "run-b"}}],
    eval_set_cases_by_run={
        "run-a": [
            {"case": {"id": "case-a", "title": "A"}, "case_version": {"id": "case-a-v1", "version_number": 1}},
            {"case": {"id": "case-b", "title": "B"}, "case_version": {"id": "case-b-v1", "version_number": 1}},
        ],
        "run-b": [
            {"case": {"id": "case-a", "title": "A"}, "case_version": {"id": "case-a-v2", "version_number": 2}},
            {"case": {"id": "case-b", "title": "B"}, "case_version": {"id": "case-b-v1", "version_number": 1}},
        ],
    },
    results_by_run={
        "run-a": [{"case_version_id": "case-a-v1", "passed": False, "score": 0}],
        "run-b": [
            {"case_version_id": "case-a-v2", "passed": True, "score": 1},
            {"case_version_id": "case-b-v1", "passed": True, "score": 1},
        ],
    },
)
```

Expected: `case-a` 有 v1/v2 两个版本，`case-b` 只保留一个 v1；缺失的 `run-a/case-b-v1` 不生成 cell。

- [ ] **Step 2: 验证红灯**

Run:

```bash
cd apps/api && UV_NO_CACHE=1 uv run pytest tests/test_run_matrix.py
```

Expected: FAIL with import/module not found。

### Task 3: 实现 builder 并接入 repository

**Files:**
- Create: `apps/api/skillhub/application/run_matrix.py`
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`

- [ ] **Step 1: 新增纯函数 builder**

实现 `build_eval_run_matrix`，输出现有 `skill/runs/cases/cells` shape。

- [ ] **Step 2: repository 改成查询后调用 builder**

`eval_run_matrix_for_skill` 中保留 `_filtered_eval_run_rows`、`_eval_run_context_row`、`_eval_set_cases` 和 `case_results` 查询，删除本地 cases/cells 组装循环。

### Task 4: 验证和提交

**Files:**
- Modify: `.agent/tasks/TASK-078.json`
- Modify: `.agent/logs/LOG.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`

- [ ] **Step 1: 目标验证**

Run:

```bash
cd apps/api && UV_NO_CACHE=1 uv run pytest tests/test_run_matrix.py
cd apps/api && UV_NO_CACHE=1 uv run pytest tests/test_sql_repository.py -k eval_run_matrix
cd apps/api && UV_NO_CACHE=1 uv run pytest tests/test_api_commands.py -k eval_run_matrix
```

Expected: all passed。

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
jq empty .agent/tasks.json .agent/tasks/TASK-078.json
```

Expected: all passed。
