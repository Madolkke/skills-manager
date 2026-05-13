# 基础格式校验第一阶段设计

## 背景

TASK-051 已经把服务端字段错误通过 `field_errors` 回填到前端表单。本轮继续补最常见的格式错误：用户新建 skill 时填了不稳定的 Skill ID，或 tag 中混入空格等无法作为稳定约束查询的字符。

## 外部依据

- GOV.UK Error Summary 要求有验证错误时始终展示 error summary，并把链接指向具体字段。
- MDN 表单校验指南强调客户端校验只能改善交互体验，不能替代服务端校验。
- SkillHub 的 `SKILL.md` import parser 已经要求标准 skill name 是小写字母、数字和连字符；手工新建 skill 应该和导入规则保持一致。

## 规则

### Skill ID

- 字段：`slug`
- 规则：`^[a-z0-9][a-z0-9-]{0,63}$`
- 用户文案：`Skill ID 只能使用小写字母、数字和连字符，且必须以字母或数字开头，最多 64 个字符。`

### 约束标签

- 字段：`tags`
- 规则：每个 tag 必须 1 到 64 个字符，只能使用字母、数字、`.`、`_`、`-`。
- 空列表文案：`至少填写一个约束标签。`
- 格式文案：`约束标签只能使用字母、数字、点、下划线和连字符，每个最多 64 个字符。`

## 前端策略

不新增客户端格式校验。前端继续只做 required 摘要，格式错误由服务端权威判断，再通过 `ApiError.fieldErrors` 回填到当前表单字段。这样可以避免前后端规则分叉，也能保证直接 API 调用得到同样约束。

## 范围

本阶段覆盖：

- `POST /api/skills` 的 `slug` 和 `tags`。
- `PATCH /api/skills/{skill_id}` 的 `slug`。
- `POST /api/skill-imports` 和 `POST /api/variants` 的 `tags`。
- request validation 中 `tags[0]` 这类 item 错误回填到顶层 `tags` 表单字段。

暂不覆盖：

- bundle frontmatter 的逐字段错误。
- 批量 case 行级错误。
- 所有长文本字段的长度上限。
- 客户端预提交格式提示。

## 验收

- API 红测先失败于非法 slug/tag 能创建成功、空 tags 文案泛化。
- E2E 红测先失败于非法 Skill ID 没有表单错误摘要。
- 绿色后，非法 Skill ID 会显示到 Launchpad 错误摘要和 `Skill ID` 字段旁。
