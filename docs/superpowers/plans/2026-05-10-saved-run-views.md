# Saved Run Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户能在历史页保存、应用、删除当前测评历史筛选视图。

**Architecture:** 后端新增 `saved_views` 读写模型，只保存视图配置，不复制 run 结果。前端在 `HistoryPane` 顶部加入保存视图控件，应用视图时复用现有 `runFilters`，因此 run 列表和矩阵沿用当前加载逻辑。

**Tech Stack:** FastAPI、SQLAlchemy Core、SQLite/PostgreSQL schema、Next.js React、Playwright。

---

### Task 1: 后端保存视图模型

**Files:**
- Modify: `apps/api/skillhub/infrastructure/db/tables.py`
- Modify: `apps/api/skillhub/infrastructure/db/schema.sql`
- Modify: `apps/api/migrations/versions/0001_initial_schema.py`
- Test: `apps/api/tests/test_sql_repository.py`
- Test: `apps/api/tests/test_api_commands.py`

- [ ] 先写 repository 和 API 失败测试，覆盖创建、列出、删除、配置规范化。
- [ ] 新增 `saved_views` table、PostgreSQL DDL、migration downgrade 顺序。
- [ ] 在 `SqlSkillRepository` 增加 `list_saved_views`、`create_saved_view`、`delete_saved_view`。
- [ ] 在 FastAPI 增加 `GET /api/skills/{skill_id}/saved-views`、`POST /api/saved-views`、`DELETE /api/saved-views/{saved_view_id}`。
- [ ] 跑 `cd apps/api && uv run pytest`。

### Task 2: 前端保存视图交互

**Files:**
- Modify: `apps/web/lib/types.ts`
- Create: `apps/web/components/saved-views/saved-run-views.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`
- Test: `apps/web/e2e/skills-workbench.spec.ts`

- [ ] 先写 E2E：保存筛选视图、切换筛选、应用保存视图、删除保存视图。
- [ ] 增加 `SavedView` 类型和 `SavedRunViews` 控件。
- [ ] `DecisionWorkbench` 加载保存视图，提供创建、应用、删除操作。
- [ ] 历史页将保存视图控件放在筛选器前方，保持 run 列表和矩阵复用同一组筛选。
- [ ] 跑 `cd apps/web && npm run typecheck`、`cd apps/web && npm run build`、`cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e`。

### Task 3: 文档、审计、提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `docs/product-ux-review.md`
- Modify: `.agent/tasks.json`
- Create: `.agent/tasks/TASK-012.json`
- Modify: `.agent/logs/LOG.md`

- [ ] 更新 README 的历史页能力说明。
- [ ] 更新产品审计和 UX review，把保存视图标为已完成的一步。
- [ ] 登记 TASK-012 并记录验证命令。
- [ ] 跑 `git diff --check`。
- [ ] 使用 Conventional Commit 提交并推送。

