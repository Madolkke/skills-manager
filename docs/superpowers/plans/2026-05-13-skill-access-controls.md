# Skill 作用域访问控制实施计划

> **给执行代理的说明：** 按任务逐项执行，步骤用 checkbox（`- [ ]`）追踪。

**目标：** 为 SkillHub 增加 skill 作用域角色管理，并保护 promotion 与 accepted verification。

**架构：** 复用现有 `role_assignments` 表，不新增 schema。后端在 `SqlSkillRepository` 中集中实现 role grant/list/revoke 和 permission checks；API 只暴露窄命令。前端新增独立 `SkillAccessPanel`，避免继续膨胀现有设置组件。

**技术栈：** FastAPI、SQLAlchemy Core、Next.js client components、Playwright E2E。

---

### Task 1: 红色 API 测试

**涉及文件：**
- 修改：`apps/api/tests/test_api_commands.py`

- [x] **步骤 1：写角色列表和授予测试**

新增测试：创建 skill 后 `GET /api/skills/{skill_id}/role-assignments` 应返回 `tester owner`；owner 通过 `POST /api/skills/{skill_id}/role-assignments` 授予 `qa-reviewer evaluator`；skill detail 也返回该 role assignment；`DELETE /api/role-assignments/{id}` 使用请求级 actor 后列表不再包含 `qa-reviewer`。

- [x] **步骤 2：写受保护动作测试**

新增测试：viewer 调用 `/api/variants/promotions` 返回 403；viewer 调用 `/api/eval-runs/accepted-verifications` 返回 403；maintainer 调用 accepted verification 返回 200。

- [x] **步骤 3：验证红灯**

运行：

```bash
cd apps/api && uv run pytest tests/test_api_commands.py -k "role or permission or verification" -q
```

预期：FAIL，因为 API 和 permission checks 尚不存在。

### Task 2: 后端权限实现

**涉及文件：**
- 修改：`apps/api/skillhub/domain/errors.py`
- 新增：`apps/api/skillhub/domain/permissions.py`
- 修改：`apps/api/skillhub/api/main.py`
- 修改：`apps/api/skillhub/infrastructure/db/repositories.py`

- [x] **步骤 1：新增 PermissionDeniedError**

在 `errors.py` 中新增 `PermissionDeniedError`，API 映射为 403。

- [x] **步骤 2：新增权限策略模块**

`permissions.py` 定义 roles、permissions 和 helper：

```python
ROLE_PERMISSIONS = {
    "owner": {"role.manage", "variant.promote", "verification.accept"},
    "maintainer": {"variant.promote", "verification.accept"},
    "evaluator": set(),
    "viewer": set(),
}
```

- [x] **步骤 3：skill 创建时授予 owner**

`create_skill` 在同一事务中插入 `role_assignments`：`subject_type=user`、`subject_id=actor`、`resource_type=skill`、`resource_id=skill_id`、`role=owner`。

- [x] **步骤 4：实现 role API repository 方法**

新增 `list_skill_role_assignments`、`assign_skill_role`、`revoke_role_assignment`。授予/撤销需要 `role.manage`，撤销最后一个 owner 抛错。

- [x] **步骤 5：加受保护动作门禁**

`promote_variant_version` 调用 `_require_skill_permission(..., "variant.promote")`；`accept_eval_run_verification` 调用 `_require_skill_permission(..., "verification.accept")`。

### Task 3: 红色 E2E

**涉及文件：**
- 修改：`apps/web/e2e/skills-workbench.spec.ts`

- [x] **步骤 1：写访问控制面板 E2E**

新增测试：导入 skill 后概览页显示 `访问控制`，包含 `product-operator` 和 `Owner`；添加 `qa-reviewer` 为 `Evaluator`；再移除该角色。

- [x] **步骤 2：验证红灯**

运行：

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "access roles"
```

预期：FAIL，因为前端面板尚不存在。

### Task 4: 前端访问控制面板

**涉及文件：**
- 修改：`apps/web/lib/types.ts`
- 新增：`apps/web/components/skills/skill-access-panel.tsx`
- 修改：`apps/web/components/decision-workbench.tsx`
- 修改：`apps/web/app/globals.css`

- [x] **步骤 1：扩展类型**

新增 `RoleAssignment`，并在 `SkillDetail` 上添加 `role_assignments: RoleAssignment[]`。

- [x] **步骤 2：新增 SkillAccessPanel**

组件渲染角色列表、添加表单和移除按钮；文案使用中文，role label 显示英文 role 以贴近 API。

- [x] **步骤 3：接入 overview**

`DecisionWorkbench` 新增 `assignSkillRole` 和 `revokeSkillRole`，通过 `apiSend` 调用新 API，并在成功后刷新当前 skill。

- [x] **步骤 4：样式**

添加 `.skillAccessPanel`、`.skillAccessRows`、`.skillAccessRow`、`.skillAccessForm` 样式，保持与 settings panel 一致。

### Task 5: 文档、验证和提交

**涉及文件：**
- 修改：`README.md`
- 修改：`docs/product-ux-review.md`
- 修改：`docs/product-completion-audit-2026-05-08.md`
- 修改：`.agent/logs/LOG.md`
- 修改：`.agent/tasks.json`
- 新增：`.agent/tasks/TASK-020.json`

- [x] **步骤 1：更新文档**

用中文记录 skill 作用域角色、受保护动作和本地 actor 限制。

- [x] **步骤 2：完整验证**

运行：

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

预期：全部通过。

- [x] **步骤 3：提交**

设置 TASK-020 complete / passes true，提交 `feat: add skill access controls`。
