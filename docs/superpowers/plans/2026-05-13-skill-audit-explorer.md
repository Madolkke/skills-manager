# Skill 审计事件 Explorer 实施计划

> **给执行代理的说明：** 按任务逐项执行，步骤用 checkbox（`- [x]`）追踪。

**目标：** 把治理面板里的最近事件扩展成可过滤、可检查 payload 的当前 skill 审计 Explorer。

**架构：** 后端继续复用 `audit_events` 表，通过 skill、variant、eval_run 资源关系构建 skill-scoped read model。前端新增独立 `SkillAuditExplorer` 组件，`DecisionWorkbench` 只负责 mode、filters 和数据加载。

**技术栈：** FastAPI、SQLAlchemy Core、Next.js client components、Playwright E2E、pytest。

---

### Task 1: 红色 API 测试

**涉及文件：**
- 修改：`apps/api/tests/test_api_commands.py`

- [x] **步骤 1：写 related resource audit 测试**

新增测试：创建 skill、case、candidate version、candidate run，执行 promotion 和 accepted verification；`GET /api/skills/{skill_id}/audit-events` 应包含 `variant.promoted` 和 `eval_run.accepted_verification_set`。

- [x] **步骤 2：写 filter 测试**

同一测试中校验 `action=variant.promoted` 只返回 promotion event，`resource_type=eval_run` 只返回 accepted verification event，`actor=tester` 返回当前 actor 事件。

- [x] **步骤 3：验证红灯**

运行：

```bash
cd apps/api && uv run pytest tests/test_api_commands.py -k "audit_events_include_related" -q
```

预期：失败，因为当前 read model 只返回 `resource_type=skill` 事件，且 endpoint 尚不支持过滤。

### Task 2: 后端 read model

**涉及文件：**
- 修改：`apps/api/skillhub/infrastructure/db/repositories.py`
- 修改：`apps/api/skillhub/api/main.py`

- [x] **步骤 1：扩展 repository 签名**

`list_skill_audit_events(skill_id, limit=50, actor=None, action=None, resource_type=None)`。

- [x] **步骤 2：扩展 `_skill_audit_events`**

查询当前 skill 的 `skill`、`variant`、`eval_run` 相关 audit events，并叠加 actor/action/resource_type 条件。

- [x] **步骤 3：扩展 API endpoint**

`GET /api/skills/{skill_id}/audit-events` 接收 `actor`、`action`、`resource_type`、`limit`，limit clamp 到 1..200。

- [x] **步骤 4：验证 API 绿色**

运行：

```bash
cd apps/api && uv run pytest tests/test_api_commands.py -k "audit_events_include_related" -q
```

### Task 3: 前端审计 Explorer

**涉及文件：**
- 新增：`apps/web/components/skills/skill-audit-explorer.tsx`
- 修改：`apps/web/components/skills/skill-governance-panel.tsx`
- 修改：`apps/web/components/decision-workbench.tsx`
- 修改：`apps/web/app/globals.css`

- [x] **步骤 1：新增组件**

`SkillAuditExplorer` 展示摘要、actor/action/resource_type filters、事件列表和 payload JSON 详情。

- [x] **步骤 2：接入 mode**

`Mode` 新增 `audit`；导航、命令菜单和治理面板入口可打开审计视图。

- [x] **步骤 3：加载数据**

进入 audit mode 时请求 `/api/skills/{skill_id}/audit-events?limit=100...`，filter 变化时重新加载。

- [x] **步骤 4：样式**

新增 `.skillAuditExplorer`、`.auditExplorerFilters`、`.auditExplorerTimeline`、`.auditPayloadPanel` 等样式，保持当前工作台的紧凑、专业信息密度。

### Task 4: E2E、视觉、文档和提交

**涉及文件：**
- 修改：`apps/web/e2e/skills-workbench.spec.ts`
- 修改：`apps/web/e2e/visual-workbench.spec.ts`
- 新增：`apps/web/e2e/visual-workbench.spec.ts-snapshots/skill-audit-explorer-chromium-darwin.png`
- 修改：`README.md`
- 修改：`docs/api-contract.md`
- 修改：`docs/product-ux-review.md`
- 修改：`docs/product-completion-audit-2026-05-08.md`
- 修改：`.agent/logs/LOG.md`
- 修改：`.agent/tasks.json`
- 新增：`.agent/tasks/TASK-023.json`

- [x] **步骤 1：写 E2E**

导入 skill，添加成员产生 role audit event，从治理面板进入审计 Explorer，过滤 `role.assigned`，检查 payload。

- [x] **步骤 2：新增视觉基线**

新增 audit explorer snapshot。

- [x] **步骤 3：完整验证**

运行：

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

- [x] **步骤 4：提交**

设置 TASK-023 complete / passes true，提交：

```bash
git commit -m "feat: add skill audit explorer"
```
