# Case 历史版本恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户能从 case history 中恢复旧 `EvalCaseVersion`，并以新版本方式进入当前 eval set snapshot。

**Architecture:** 新增一个后端 restore command，内部复制旧 case version 的 artifact content 并复用现有 `create_eval_case_version` 语义。前端把 `CaseHistoryPanel` 抽成独立组件，在非当前版本上显示恢复按钮，并让 eval set 刷新时保留仍然有效的 case history 上下文。

**Tech Stack:** FastAPI、SQLAlchemy repository、Next.js React client components、TypeScript、Playwright E2E。

---

### Task 1: 红测和任务定义

**Files:**
- Add: `.agent/tasks/TASK-010.json`
- Modify: `.agent/tasks.json`
- Modify: `apps/api/tests/test_sql_repository.py`
- Modify: `apps/api/tests/test_api_commands.py`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 添加 TASK-010 定义**

记录恢复旧 case version 的范围、非目标和验证命令。

- [x] **Step 2: 写后端红测**

新增 repository 测试：创建 case v1，编辑为 v2，再 restore v1。断言当前 case 指向 v3，最新 eval set 使用 v3，旧 eval set 仍使用 v1。

新增 API 测试：`POST /api/eval-cases/{case_id}/restores` 可以恢复同 case 版本，跨 case source version 返回 400/404。

- [x] **Step 3: 写前端红测**

新增 E2E：编辑 case 后打开历史，点击旧版本 `恢复此版本`，断言历史里有 3 个版本，并且带 `当前版本` 标记的新版本恢复为旧 expected output。

- [x] **Step 4: 运行红测**

```bash
cd apps/api && uv run pytest tests/test_sql_repository.py::SqlSkillRepositoryTest::test_restore_eval_case_version_creates_new_current_version
cd apps/api && uv run pytest tests/test_api_commands.py::ApiCommandTest::test_restore_eval_case_version_from_history
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "restore an older eval case version"
```

预期：失败，因为 API 和前端按钮还不存在。

### Task 2: 后端实现

**Files:**
- Modify: `apps/api/skillhub/api/main.py`
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`

- [x] **Step 1: 新增 API payload**

`RestoreEvalCaseVersionPayload` 包含 `source_case_version_id`、`actor`、`notes`。

- [x] **Step 2: 新增 repository method**

`restore_eval_case_version(case_id, source_case_version_id, actor, notes)`：

1. 校验 source version 属于 case。
2. 读取旧 input/expected artifact content。
3. 调用 `create_eval_case_version(..., make_current=True)` 创建新版本。

- [x] **Step 3: 新增 FastAPI route**

`POST /api/eval-cases/{case_id}/restores` 调用 repository method，并返回 `result_payload`。

- [x] **Step 4: 跑后端目标测试**

```bash
cd apps/api && uv run pytest tests/test_sql_repository.py::SqlSkillRepositoryTest::test_restore_eval_case_version_creates_new_current_version tests/test_api_commands.py::ApiCommandTest::test_restore_eval_case_version_from_history tests/test_api_commands.py::ApiCommandTest::test_restore_eval_case_version_rejects_cross_case_source
```

### Task 3: 前端实现

**Files:**
- Add: `apps/web/components/eval-cases/case-history-panel.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`

- [x] **Step 1: 抽出 CaseHistoryPanel**

把现有 inline `CaseHistoryPanel` 移到独立文件，并新增 props：`currentCaseVersionId`、`busy`、`onRestoreVersion`。

- [x] **Step 2: 新增 restore command**

在 `DecisionWorkbench` 新增 `restoreCaseVersion(caseId, sourceCaseVersionId, sourceVersionNumber)`，POST restore endpoint，刷新 skill/eval set，再重新打开 case history。

- [x] **Step 3: 接入按钮**

`CaseHistoryPanel` 对非当前版本显示 `恢复此版本`，当前版本显示 `当前版本`。

- [x] **Step 4: 添加样式**

给 history header actions 增加按钮样式，保持紧凑、低噪声。

- [x] **Step 5: 跑目标 E2E**

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "restore an older eval case version"
```

结果：通过，目标场景 `operator can restore an older eval case version` 已验证。

### Task 4: 文档、验证、提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`

- [x] **Step 1: 更新文档**

README 增加 case history restore；UX review 和完成度审计移除对应缺口。

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
git commit -m "feat: restore eval case versions"
git push
```
