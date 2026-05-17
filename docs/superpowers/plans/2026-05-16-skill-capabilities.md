# Skill capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for behavior changes and superpowers:verification-before-completion before claiming completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加当前 actor 对当前 skill 的后端权威 capabilities，并让前端主要受保护动作按 capability 展示可用状态和原因。

**Architecture:** API 新增 `GET /api/skills/{skill_id}/capabilities`，Repository 复用现有 role assignment 和 `role_allows` 计算权限。前端在加载 skill 时同时加载 capabilities，并通过轻量 helper 让访问控制、promotion、diff 和 accepted verification UI 只展示当前 actor 能执行的动作。

**Tech Stack:** FastAPI、SQLAlchemy、pytest、React、Next.js、Playwright。

---

### Task 1: API capabilities 红绿测试

**Files:**
- Modify: `apps/api/tests/test_api_commands.py`

- [x] **Step 1: 写失败测试**
  - 新增 `test_skill_capabilities_reflect_actor_roles`。
  - 创建 skill 后，`tester` 应有 `role.manage`、`variant.promote`、`verification.accept`。
  - 给 `capability-viewer` 授予 `viewer` 后，用 `X-SkillHub-Actor: capability-viewer` 调 endpoint，应看到 roles 为 `["viewer"]` 且三项权限都是 `false`。
  - 再授予 `maintainer` 后，应看到 `variant.promote` 和 `verification.accept` 为 `true`，`role.manage` 仍为 `false`。

- [x] **Step 2: 跑红灯**
  - Run: `cd apps/api && UV_NO_CACHE=1 uv run pytest tests/test_api_commands.py -k "skill_capabilities"`
  - Expected: FAIL，当前 endpoint 不存在。

### Task 2: 后端 capabilities API

**Files:**
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`
- Modify: `apps/api/skillhub/api/main.py`

- [x] **Step 1: 增加 Repository 方法**
  - 新增 `skill_capabilities(self, *, skill_id: str, actor: str, subject_type: str = "user")`。
  - 调用 `_skill_row` 确认 skill 存在。
  - 用 `_actor_skill_roles` 获取角色。
  - 返回 `actor`、`subject_type`、`roles`、`permissions`。

- [x] **Step 2: 增加 API endpoint**
  - 新增 `GET /api/skills/{skill_id}/capabilities`。
  - 使用 `actor_dependency`。
  - 返回 repository 结果。

- [x] **Step 3: 跑 API 绿灯**
  - Run: `cd apps/api && UV_NO_CACHE=1 uv run pytest tests/test_api_commands.py -k "skill_capabilities"`
  - Expected: PASS。

### Task 3: 前端 capability-aware UI

**Files:**
- Modify: `apps/web/lib/types.ts`
- Create: `apps/web/lib/capabilities.ts`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/components/overview/workbench-overview-pane.tsx`
- Modify: `apps/web/components/skills/skill-access-panel.tsx`
- Modify: `apps/web/components/variants/workbench-variants-pane.tsx`
- Modify: `apps/web/components/diff/workbench-diff-pane.tsx`
- Modify: `apps/web/components/history/workbench-history-pane.tsx`
- Modify: `apps/web/components/run-comparison/run-comparison-panel.tsx`
- Modify: `apps/web/components/promotion-review/promotion-review-pane.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 写 E2E 红测**
  - 导入 skill 并追加一个 candidate version。
  - 在访问控制里给 `capability-viewer` 添加 `viewer`。
  - 切换本地 actor 为 `capability-viewer`。
  - 断言 Access panel 显示 `当前角色 Viewer`、`不能管理角色`，添加成员按钮 disabled。
  - 进入变体页，断言 `设为当前版本评审` 按钮 disabled 且有原因。

- [x] **Step 2: 增加类型和 helper**
  - `SkillCapabilities` 类型包含 `actor`、`subject_type`、`roles`、`permissions`。
  - `canUseCapability(capabilities, permission)` 返回 boolean。
  - `capabilityDeniedReason(permission)` 返回中文原因。

- [x] **Step 3: DecisionWorkbench 加载 capabilities**
  - 新增 `capabilities` state。
  - `loadSkill` 对非 empty skill 并行请求 detail 和 capabilities。
  - empty skill 设置为 null。
  - 切换 actor 或角色变更后复用现有 `loadSkills` 刷新 capabilities。

- [x] **Step 4: 传递 capability 到受保护 UI**
  - Overview/Access panel 显示角色和能力。
  - Variants/Diff 的 promotion review 入口在没有 `variant.promote` 时 disabled。
  - Promotion review 的最终 promote button 在没有 `variant.promote` 时 disabled 并显示原因。
  - Run comparison 的 accepted verification button 在没有 `verification.accept` 时 disabled 并显示原因。

- [x] **Step 5: 跑目标 E2E 绿灯**
  - Run: `cd apps/web && npm run e2e -- skills-workbench.spec.ts -g "capabilities"`
  - Expected: PASS。

### Task 4: 文档、完整验证、提交

**Files:**
- Modify: `README.md`
- Modify: `docs/api-contract.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-ux-friction-audit-2026-05-14.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Create: `.agent/tasks/TASK-062.json`

- [x] **Step 1: 更新中文文档和任务记录**
  - 写清 capabilities endpoint 和 capability-aware UI。

- [x] **Step 2: 完整验证**
  - `cd apps/api && UV_NO_CACHE=1 uv run pytest`
  - `cd apps/web && npm run test:unit`
  - `cd apps/web && npm run typecheck`
  - `cd apps/web && npm run build`
  - `cd apps/web && npm audit --omit=dev`
  - `cd apps/web && npm run e2e`
  - `git diff --check`
  - `jq empty .agent/tasks.json .agent/tasks/TASK-062.json`
