# Workspace Skill Launchpad Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让空工作台在主内容区直接完成标准 Skill bundle 导入或空白 skill 创建，减少 first-run 对右侧 inspector 的依赖。

**Architecture:** 新增 `SkillLaunchpad` client component，复用 `DecisionWorkbench` 中已有的 `importSkill`、`createSkill`、`refreshImportPreview` 表单处理函数。`OverviewPane` 在 `!hasPersistedSkill` 时渲染 launchpad，而不是只显示两个跳转按钮；右侧 inspector 路径保持不变。

**Tech Stack:** Next.js client components、现有 FastAPI API、Playwright E2E。

---

### Task 1: 红色 E2E

**Files:**
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 新增主区导入测试**

新增测试 `operator can import a skill from the workspace launchpad`：空工作台进入 `/skills`，在 `.skillLaunchpad` 的导入模式填写 owner/tags/variant label，选择 folder bundle，提交后断言新 skill heading 和导入成功提示。

- [x] **Step 2: 新增主区创建测试**

新增测试 `operator can create a blank skill from the workspace launchpad`：空工作台进入 `/skills`，在 `.skillLaunchpad` 切换到 `新建 skill`，填写字段并提交，断言新 skill heading 和 default variant。

- [x] **Step 3: 更新视觉基线**

复用现有 `visual baseline: empty skill workbench`，更新空工作台截图，确保 first-run UI 不退回到只有两个小按钮。

- [x] **Step 4: 验证红灯**

Run:

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "workspace launchpad"
```

Expected: FAIL，因为 `.skillLaunchpad` 尚不存在。

### Task 2: Launchpad 组件

**Files:**
- Create: `apps/web/components/skills/skill-launchpad.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`

- [x] **Step 1: 新建 `SkillLaunchpad`**

组件接收 `busy`、`importPreview`、`onCreateSkill`、`onImportSkill`、`onRefreshImportPreview`，内部用 segmented control 切换导入和创建模式。

- [x] **Step 2: 接入 `OverviewPane`**

将 `importSkill`、`createSkill`、`refreshImportPreview`、`importPreview`、`busy` 传入 `OverviewPane`；空状态渲染 `SkillLaunchpad` 和闭环 checklist。

- [x] **Step 3: 样式**

新增 `.skillLaunchpad` 系列样式，让 first-run 主区呈现为清晰 onboarding 面板，而不是普通表单堆叠。

### Task 3: 文档和验证

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Modify: `.agent/tasks/TASK-017.json`

- [x] **Step 1: 文档**

README 说明可在主工作区 launchpad 导入或创建 skill；UX review 记录 Vercel/GitHub/Linear/Raycast 借鉴；完成度审计更新已完成项和剩余摩擦。

- [x] **Step 2: 验证**

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

设置 TASK-017 complete / passes true，提交 `feat: launch skills from workspace`。
