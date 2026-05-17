# Skill capabilities 权限感知设计

## 背景

SkillHub 已有 skill 作用域角色和后端权限门禁，但前端仍主要靠本地 actor 面板和角色列表让用户推断自己能做什么。对成熟产品来说，用户不应该点到 promotion、accepted verification 或访问控制后才从 403 里知道自己没有权限。真实认证接入前，需要先把“当前 actor 对当前 skill 的能力”做成后端权威读模型，前端只负责展示和禁用。

## 外部依据

- GitLab project members 文档把成员、角色和可执行动作绑定在一起，并说明添加/管理成员需要 Owner 或 Maintainer 等足够角色：https://docs.gitlab.com/user/project/members/
- GitLab predefined roles 文档把角色视为权限集合，且同一用户可能从多处获得角色，最终权限由角色集合决定：https://docs.gitlab.com/development/permissions/predefined_roles/
- GitHub protected branches 文档强调关键写入动作必须由服务端规则阻断，例如缺少 review 或 status check 时不能合并：https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches

## 方案

- 新增 `GET /api/skills/{skill_id}/capabilities`，用请求级 actor context 计算当前 actor 在该 skill 上的角色和权限。
- 返回稳定权限 key：`role.manage`、`variant.promote`、`verification.accept`。
- 前端在切换 skill、切换 actor、角色变更后加载 capabilities，并传给 Overview、Variants、Diff、History 和 Promotion review。
- `SkillAccessPanel` 显示当前 actor 的角色和三项能力；没有 `role.manage` 时禁用添加/移除角色，并说明需要 Owner。
- `WorkbenchVariantsPane`、`WorkbenchDiffPane`、`PromotionReviewPane` 和 `RunComparisonPanel` 根据 capabilities 禁用受保护动作，并显示简短原因。
- 后端权限门禁不改变；capabilities 只是提前解释，不替代 403。

## 范围

本阶段覆盖：

- 当前 actor 的 skill scoped capabilities API。
- 前端主要受保护动作的禁用和原因提示。
- API 与 E2E 红绿测试。
- README、API contract、产品审计和任务记录更新。

暂不覆盖：

- 真正的登录/OIDC/JWT。
- 组织级角色继承。
- 自定义角色。
- 细到按钮级的全部低频 admin action。

## 验收

- API 红测先失败于 `/api/skills/{id}/capabilities` 不存在。
- E2E 红测先失败于切换到 viewer 后访问控制仍允许添加成员、promotion 入口仍可直接操作。
- 绿色后：viewer 能看到自己是 Viewer，不能管理角色、不能 promote、不能接受验证依据；owner/maintainer 能看到对应能力。
- 完整测试、构建、E2E 和文档校验通过后提交推送。
