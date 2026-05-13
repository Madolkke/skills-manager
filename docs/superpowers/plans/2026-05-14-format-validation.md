# 基础格式校验第一阶段 Implementation Plan

**Goal:** 在 `field_errors` 契约上补齐 Skill ID 和 tags 的基础格式校验。

## Steps

- [x] **Step 1: 任务登记和红测**
  - 新增 `.agent/tasks/TASK-052.json` 并登记到 `.agent/tasks.json`。
  - API 测试覆盖非法 slug、非法 tag、空 tags。
  - E2E 测试覆盖 Launchpad 非法 Skill ID 回填字段。

- [x] **Step 2: 后端校验规则**
  - 用 Pydantic `Annotated + Field(pattern/min_length/max_length)` 定义 `SkillSlug`、`TagValue` 和 `TagsPayload`。
  - 复用到 create skill、update skill、import skill 和 create variant payload。
  - request validation 将 tag item 错误映射回顶层 `tags` 字段。

- [x] **Step 3: 错误文案映射**
  - 为 slug pattern/length 错误输出稳定中文文案。
  - 为 tags 空列表和 tag pattern/length 错误输出稳定中文文案。

- [x] **Step 4: 文档与验证**
  - 更新 README、API contract、产品体验评审、完成度审计、摩擦审计、任务日志和本任务规格。
  - 运行 API、unit、typecheck、build、audit、E2E、diff check 和 JSON 校验。

## Rollback

如果新格式规则误伤已有合法数据，先放宽对应 `Field(pattern=...)`，保留 `field_errors` 契约和错误摘要展示。不要回退 TASK-051 的通用错误映射。
