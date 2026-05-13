# Workspace Skill Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户在 skill 概览主工作区直接编辑 skill 身份和默认分发 variant。

**Architecture:** 扩展 `PATCH /api/skills/{skill_id}`，让 skill 元数据更新可以同时移动 `default_variant_id` 指针，并在 repository 层校验 variant 属于同一 skill。前端新增 `SkillSettingsPanel`，复用现有 `updateSkill` 数据流，overview 主区和 inspector 都使用同一个 PATCH 契约。

**Tech Stack:** FastAPI、SQLAlchemy repository、Next.js client components、Playwright E2E。

---

### Task 1: 红色后端测试

**Files:**
- Modify: `apps/api/tests/test_api_commands.py`

- [x] **Step 1: 测试 PATCH 可以切换默认 variant**

在 `test_management_flow_updates_variant_and_cases` 附近新增断言：创建第二个 variant 后调用 `PATCH /api/skills/{skill_id}`，请求体包含 `slug`、`owner_ref`、`default_variant_id`，再读取 detail，确认 summary 的 default variant 已变更。

- [x] **Step 2: 测试拒绝跨 skill 默认 variant**

新增 API 测试：创建两个 skill，尝试把第二个 skill 的 variant 设为第一个 skill 的 default，期望 400 且错误包含 `same skill`。

- [x] **Step 3: 验证红灯**

Run:

```bash
cd apps/api && uv run pytest tests/test_api_commands.py -k "default_variant"
```

Expected: FAIL，因为 `UpdateSkillPayload` 尚不接受 `default_variant_id`，repository 也未更新指针。

### Task 2: 后端契约实现

**Files:**
- Modify: `apps/api/skillhub/api/main.py`
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`
- Modify: `docs/api-contract.md`

- [x] **Step 1: 扩展 payload**

`UpdateSkillPayload` 新增 `default_variant_id: str | None = None`。

- [x] **Step 2: 扩展 repository**

`update_skill` 接收 `default_variant_id`；如果提供，读取 variant 并检查 `variant.skill_id == skill_id`，否则抛出 `InvariantError("Default variant must belong to the same skill.")`。保存 slug、owner_ref、default_variant_id。

- [x] **Step 3: 更新 API 文档**

把 `PATCH /api/skills` 修正为 `PATCH /api/skills/{skill_id}`，请求体包含 `default_variant_id`，并说明跨 skill variant 会被拒绝。

### Task 3: 红色前端 E2E

**Files:**
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 新增主区设置测试**

新增测试：导入 skill，创建 `Strict reviewer` variant，回到概览，在主区 `.skillSettingsPanel` 修改 slug/owner，并选择 strict variant 为默认分发，保存后断言 header heading、catalog owner 和 hero 中的默认 variant 已刷新。

- [x] **Step 2: 验证红灯**

Run:

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "workspace skill settings"
```

Expected: FAIL，因为 `.skillSettingsPanel` 尚不存在。

### Task 4: 前端实现

**Files:**
- Create: `apps/web/components/skills/skill-settings-panel.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`

- [x] **Step 1: 新建组件**

`SkillSettingsPanel` 接收 `busy`、`selectedDetail`、`defaultVariant`、`latestRun`、`score`、`onUpdateSkill`，渲染 identity 表单、default variant select 和当前分发摘要。

- [x] **Step 2: 接入 overview**

`OverviewPane` 传入 `updateSkill`，在 metrics 下方渲染 `SkillSettingsPanel`。`updateSkill` 从 form 读取可选 `default_variant_id` 并发送到 API。

- [x] **Step 3: 样式**

新增 `.skillSettingsPanel` 系列样式，保持和现有 Linear-like 工作台一致：紧凑、清晰、可扫读，不引入新的大面积色块。

### Task 5: 文档、视觉和验证

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Create: `.agent/tasks/TASK-018.json`
- Modify: `apps/web/e2e/visual-workbench.spec.ts-snapshots/imported-skill-overview-chromium-darwin.png`

- [x] **Step 1: 更新视觉基线**

Run:

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "visual baseline: imported skill overview" --update-snapshots
```

- [x] **Step 2: 完整验证**

Run:

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

Expected: 全部通过。

- [x] **Step 3: 提交**

设置 TASK-018 complete / passes true，提交 `feat: edit skill settings from workspace`。
