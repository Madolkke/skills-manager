# Skill 作用域访问控制设计

日期：2026-05-13

## 背景

SkillHub 当前已经能导入标准 Skill bundle、维护 variant/version、运行手工测评、保存验证依据并执行 promotion。剩下的关键缺口是权限：`promotion` 和 `accepted verification` 都会改变用户看到的可信分发证据，不能长期依赖单用户假设。

## 外部实践

- GitHub protected branches 把重要分支变更限制在 pull request、required reviews、status checks 和可配置 bypass 规则之后。适配到 SkillHub：`Variant.current_version_id` 的移动应视为受保护动作，而不是普通字段更新。来源：<https://docs.github.com/articles/about-required-reviews-for-pull-requests>
- GitLab approval rules 支持让不具备 push/merge 权限的用户参与 approval，说明“评审/批准”和“直接写入”可以拆开授权。适配到 SkillHub：后续可以允许 evaluator 记录 run，但只有 owner/maintainer 能接受验证依据或 promotion。来源：<https://docs.gitlab.com/user/project/merge_requests/approvals/rules/>
- Vercel RBAC 区分 team role 和 project role，Contributor 只有被显式分配项目角色后才有项目访问权。适配到 SkillHub：本轮先采用 skill 作用域角色，不做全局万能 admin。来源：<https://vercel.com/docs/rbac/access-roles>
- Linear 将部分危险团队操作限制给 team owner，并且权限不从父团队自动继承到子团队。适配到 SkillHub：role assignment 必须明确绑定到 `skill`，不做隐式继承。来源：<https://linear.app/docs/members-roles>

## 设计目标

1. `role_assignments` 从 schema 里的占位表变成真实能力。
2. 创建或导入 skill 时，`actor` 自动获得该 skill 的 `owner` 角色。
3. 支持查看、授予、撤销 skill 作用域角色：`owner`、`maintainer`、`evaluator`、`viewer`。
4. `promotion` 和 `accepted verification` 需要 `owner` 或 `maintainer`。
5. 角色管理需要 `owner`。
6. 概览页显示 `访问控制` 面板，让用户知道当前 skill 的维护者是谁，并能增删成员角色。
7. 保持当前本地单用户可用：前端继续用 `product-operator` 作为 actor；正式认证接入后替换 actor 来源。

## 非目标

- 不接入登录、session、OAuth、SSO 或 SCIM。
- 不实现组织级继承、团队组、邀请邮件。
- 不把所有写操作一次性门禁；本轮只保护 `promotion`、`accepted verification` 和 role management。
- 不做 fork/PR 审批流。

## 权限语义

| 角色 | 本轮权限 |
| --- | --- |
| `owner` | 管理角色、promotion、接受验证依据 |
| `maintainer` | promotion、接受验证依据 |
| `evaluator` | 暂不新增门禁；保留给后续 eval runner / manual run 权限 |
| `viewer` | 只读语义，不能执行受保护动作 |

权限判断只看显式 `subject_type=user + subject_id=<actor> + resource_type=skill + resource_id=<skill_id>`。如果没有角色，受保护动作拒绝。

## API

- `GET /api/skills/{skill_id}/role-assignments` 返回当前 skill 的角色列表。
- `POST /api/skills/{skill_id}/role-assignments` 接收 `subject_id`、`role`、可选 `subject_type`、`actor`，由 owner 授权。
- `DELETE /api/role-assignments/{assignment_id}` 删除角色，由请求级 actor context 中的 owner 授权。

删除最后一个 owner 应被拒绝，避免把 skill 锁死。

## 前端

在 `概览` 页的 `Skill settings` 附近新增 `SkillAccessPanel`：

- 顶部说明当前 actor 和此 skill 的 access posture。
- 列表显示 subject、role、scope、created_by。
- 表单支持输入 `subject_id`，选择 role，点击 `添加成员`。
- 非 owner 行可移除；owner 行可显示但删除最后 owner 时后端拒绝。

## 测试策略

- API 测试覆盖 skill 创建后自动授予 owner。
- API 测试覆盖 owner 能授予/撤销角色，并且 skill detail 返回角色列表。
- API 测试覆盖 viewer 不能 promotion，也不能 accepted verification。
- API 测试覆盖 maintainer 可以 accepted verification。
- E2E 覆盖概览页访问控制面板能添加并移除一个 evaluator。
- 全量验证仍跑 API pytest、Web typecheck/build/E2E 和 diff check。
