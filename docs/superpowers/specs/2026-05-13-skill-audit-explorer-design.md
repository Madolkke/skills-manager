# Skill 审计事件 Explorer 设计

日期：2026-05-13

## 背景

`治理与审计` 面板已经把归档从 inspector 移到了概览主区，也能显示最近几条 skill 级 audit events。但成熟产品里，用户不只是看最近事件，还要回答“谁改了权限”“哪个动作移动了当前分发”“这次 accepted verification 对应哪个 run”。因此下一步需要一个当前 skill 范围内的审计 Explorer。

## 外部实践

- Linear Audit Log 支持浏览最近事件，并按 event type、actor 和 metadata 查询；适配到 SkillHub：先做当前 skill 的 action/actor/resource_type 过滤，而不是一开始做组织级审计。来源：<https://linear.app/docs/audit-log>
- GitHub Enterprise Audit Log 支持用 `actor`、`action`、`repo`、`created` 等限定查询；适配到 SkillHub：审计查询应基于结构化字段，而不是全文搜索。来源：<https://docs.github.com/enterprise/admin/guides/user-management/auditing-users-across-an-organization>
- Stripe Workbench Logs/Events 支持按 source、status、resource ID、event type 过滤，并在右侧检查 payload；适配到 SkillHub：审计列表和 payload 详情应并排展示，方便排查变更原因。来源：<https://docs.stripe.com/workbench/guides>

## 产品方案

新增 `审计` 工作区 mode，但不把它放成主要高频入口。用户可以从治理面板点击 `查看全部审计`，也可以通过 `Cmd/Ctrl+K` 搜索 `打开审计`。页面采用三段结构：

1. 顶部摘要：当前筛选下的事件数、actor 数、资源类型数、关键动作数。
2. 过滤条：`actor` 文本输入、`action` 文本输入、`resource_type` 下拉、清除筛选。
3. 主体：左侧事件时间线，右侧选中事件详情和 JSON payload。

## 后端方案

当前 `audit_events` 表没有 `skill_id` 字段，所以 read model 用资源关系反查当前 skill：

- `resource_type=skill` 且 `resource_id=skill_id`
- `resource_type=variant` 且 `resource_id` 属于当前 skill 的 variant
- `resource_type=eval_run` 且 `resource_id` 属于当前 skill 的 eval run

`GET /api/skills/{skill_id}/audit-events` 新增查询参数：

- `limit`：默认 50，上限 200。
- `actor`：精确匹配 `actor_ref`。
- `action`：精确匹配 `action`。
- `resource_type`：精确匹配 `resource_type`。

`GET /api/skills/{skill_id}` 仍只带最近 10 条，供概览治理面板使用。

## 非目标

- 不做跨 skill / 组织级审计。
- 不做导出、保留策略和 SIEM webhook。
- 不修改 audit event schema；后续正式迁移可以考虑补 `skill_id` 冗余列提高查询效率。

## 测试策略

- API 测试：promotion 和 accepted verification 这类 `variant/eval_run` 资源事件会出现在当前 skill audit endpoint 中，并且 action/resource_type filter 可用。
- E2E 测试：用户从治理面板进入审计 Explorer，能看到 role event，输入 action filter 后列表收窄，选中事件后看到 payload。
- 视觉回归：新增 `skill-audit-explorer.png`，覆盖摘要、过滤条、事件列表和 payload 详情。
