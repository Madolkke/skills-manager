# 去 Variant 化与 EvalRun 运行环境设计

日期：2026-05-26

## 1. 背景

当前正式版把 tags 放在 `Variant` 上，并用 `VariantVersion` 表示 skill bundle 的不可变版本。这个模型在早期有用，因为它把“某组 tags 下的当前最优解”作为维护对象。但现在已经确认这些 tags 的真实含义是运行环境，例如 runner、model、OS、sandbox 或浏览器窗口，而不是不同的 skill 内容分支。

因此 `Variant` 会让用户误解：同一个 Skill 在不同环境运行时，看起来像需要维护多套 Skill 内容。正确模型应该是：Skill 内容版本是一条直接属于 Skill 的版本线；运行环境属于一次 EvalRun。

## 2. 决策

直接去 Variant 化，不做兼容过渡 UI。

新的核心链路：

```text
Skill -> SkillVersion -> EvalRun(run_context) + EvalSetVersion
```

关键语义：

- `Skill` 是稳定入口。
- `SkillVersion` 是不可变 skill bundle 内容快照，替代 `VariantVersion`。
- `Skill.current_version_id` 指向当前默认使用的 `SkillVersion`。
- `EvalRun.skill_version_id` 绑定被测内容版本。
- `EvalRun.environment_tags` 和 `EvalRun.run_context` 记录本次运行环境。
- `EvalSetVersion`、`EvalCaseVersion`、`CaseResult` 继续保持不可变证据语义。
- `AcceptedVerification` 改为接受某个 `SkillVersion + EvalSetVersion + run_context_hash` 下的一次 finished run。
- Bundle diff 比较两个 `SkillVersion` 的不可变 bundle artifact。

## 3. 非目标

- 不重新开放旧 `apps/web` 工作台。
- 不做多内容分支、channel、track 或 release train。一个 Skill 先只有一条内容版本线。
- 不保留用户可见的 Variant 页面、Variant tags 或 VariantVersion 文案。
- 不把运行环境 tags 放回 Skill、SkillVersion 或 EvalSet。
- 不实现复杂自动 runner 调度；本轮只要求手工 eval 记录环境上下文。

## 4. 数据模型

### 4.1 `skills`

新增：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `current_version_id` | text? | 当前 SkillVersion 指针。 |

移除：

| 字段 | 处理 |
| --- | --- |
| `default_variant_id` | 删除；默认入口直接由 `current_version_id` 表示。 |

约束：

- `skills.current_version_id + skills.id` 必须引用同一 skill 下的 `skill_versions(id, skill_id)`。

### 4.2 `skill_versions`

替代 `variant_versions`。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | text | 不可变版本 ID。迁移时可以复用旧 `variant_versions.id`，新写入使用 `skillver_` 前缀。 |
| `skill_id` | text | 所属 Skill。 |
| `version_number` | integer | 该 Skill 下线性版本号。 |
| `content_ref` | json/jsonb | bundle artifact locator。 |
| `content_digest` | text | bundle 内容 digest。 |
| `change_summary` | text | 本次版本说明。 |
| `created_at` | timestamptz | 创建时间。 |
| `created_by` | text | 创建者。 |

约束：

- `unique(skill_id, version_number)`。
- `unique(id, skill_id)`。
- 创建后不更新内容字段。

### 4.3 删除 `tag_sets` / `variants` / `variant_versions`

`tag_sets` 不再作为核心模型存在。环境标签直接挂在 EvalRun 上，不需要独立 tag set 表。

删除表：

- `tag_sets`
- `variants`
- `variant_versions`

### 4.4 `eval_runs`

变更：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `skill_version_id` | text | 替代 `variant_version_id`。 |
| `environment_tags` | text[] / sqlite json | 排序去重后的运行环境标签。 |
| `run_context` | json/jsonb | 结构化运行上下文，例如 `{ "runner": "codex", "model": "gpt-5.4", "os": "windows" }`。 |
| `run_context_hash` | text | 由 normalized `environment_tags + run_context` 计算，用于过滤和 accepted verification 唯一性。 |

兼容规则：

- API 请求体不接受 `variant_version_id`。
- API 请求体使用 `skill_version_id`。
- `environment_tags` 可以为空，但 UI 要提供显式输入。
- `run_context` 默认为 `{}`。
- `run_context_hash` 由后端计算，不信任前端传入。

### 4.5 `accepted_verifications`

变更：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `skill_version_id` | text | 被接受 run 绑定的 SkillVersion。 |
| `eval_set_version_id` | text | 被验证的 EvalSetVersion。 |
| `run_context_hash` | text | 被验证的环境上下文 hash。 |
| `eval_run_id` | text | 被接受的 finished run。 |

删除：

- `variant_id`
- `variant_version_id`

唯一约束：

```text
unique(skill_id, skill_version_id, eval_set_version_id, run_context_hash)
```

原因：同一个 SkillVersion 在 Windows/Codex 和 macOS/OpenCode 下可以分别有被接受的验证依据。

### 4.6 Promotion / release 决策

旧 `promotion_decisions` 与 `variant_id` 强绑定，不适合保留。正式 Web V4 当前也没有暴露 promotion review 主流程。本轮直接删除旧 promotion read/write API 和表。

如果后续需要“设为当前版本”的审计决策，应新增 `skill_version_decisions`：

```text
skill_id, from_version_id, to_version_id, evidence_eval_run_id?, decision_note
```

这不进入本轮实现范围。

## 5. API 契约

### 5.1 创建 Skill

`POST /api/skill-imports`

请求：

```json
{
  "owner_ref": "product-operator",
  "source": { "kind": "files", "name": "code-reviewer", "files": [] }
}
```

行为：

- 创建 `Skill`。
- 创建 `SkillVersion v1`。
- 设置 `Skill.current_version_id = v1`。
- 创建 primary EvalSet 和空 EvalSetVersion v1。

不再接受或要求 `tags`。

### 5.2 上传 Skill 版本

`POST /api/skill-versions`

请求：

```json
{
  "skill_id": "skill_123",
  "source": { "kind": "files", "name": "code-reviewer", "files": [] },
  "make_current": true
}
```

行为：

- 创建新的不可变 `SkillVersion`。
- 如果 `make_current=true`，移动 `Skill.current_version_id`。

### 5.3 记录 EvalRun

`POST /api/eval-runs`

请求：

```json
{
  "skill_version_id": "skillver_123",
  "eval_set_version_id": "evalsetver_123",
  "strategy": "manual_pass_fail",
  "environment_tags": ["codex", "windows"],
  "run_context": {
    "runner": "codex",
    "os": "windows"
  },
  "results": {
    "casever_123": {
      "passed": true,
      "actual_output": "actual answer"
    }
  }
}
```

响应仍返回：

```json
{ "eval_run_id": "evalrun_123" }
```

### 5.4 Bundle diff

`GET /api/artifacts/diff?left_skill_version_id=&right_skill_version_id=`

返回结构保持 summary/files/hunks 不变，但 `left/right` 字段改为：

```json
{
  "left": { "skill_version_id": "skillver_1", "version_number": 1, "content_digest": "..." },
  "right": { "skill_version_id": "skillver_2", "version_number": 2, "content_digest": "..." }
}
```

### 5.5 History

`GET /api/skills/{skill_id}/eval-runs`

每条 run context 返回：

- `eval_run`
- `skill_version`
- `eval_set`
- `eval_set_version`
- `environment_tags`
- `run_context`
- `accepted_verification`

不返回 `variant`。

## 6. Web V4 改动

页面结构改为：

| 原页面 | 新页面 |
| --- | --- |
| 概览 | 保留；展示 current SkillVersion、bundle 文件树、最近 accepted run。 |
| 变体 | 改名为 `版本`；展示 SkillVersion 版本线、上传版本、Bundle diff、版本详情。 |
| 测评集 | 保留。 |
| 测评 | 保留；选择 SkillVersion + EvalSetVersion，输入运行环境 tags/context，记录 actual output。 |
| 历史 | 保留；按 SkillVersion、EvalSetVersion、environment tags/run_context 展示证据链。 |

UI 文案规则：

- 不出现“变体”“Variant”“VariantVersion”作为用户可见概念。
- `tags` 文案只出现在 eval run 运行环境里，例如“运行环境标签”。
- Hub 卡片不显示默认 variant tags；可以显示最近验证环境。
- 上传版本不再要求 tags。

## 7. 迁移策略

本轮要支持从旧 schema 迁移到新 schema，避免已有本地 SQLite 数据直接不可读。

迁移逻辑：

1. 创建 `skill_versions`。
2. 将旧 `variant_versions` 复制到 `skill_versions`，按 `skill_id, created_at, id` 重新分配 `version_number`。
3. 新增并填充 `skills.current_version_id`：优先旧 default variant 的 current version。
4. 新增 `eval_runs.skill_version_id`，从旧 `variant_version_id` 复制。
5. 为旧 eval run 填充 `environment_tags`：读取旧 run 所属 variant 的 tag set tags。
6. 为旧 eval run 计算 `run_context_hash`。
7. 将 `accepted_verifications.variant_version_id` 迁移到 `skill_version_id`，将旧 variant tags 对应到 `run_context_hash`。
8. 删除旧 promotion 表和 variant/tag 表。

如果某个旧 Skill 没有 default variant current version，则把该 Skill 最早的 skill version 设为 current；如果没有任何版本，保留 null。

## 8. 测试策略

API：

- schema contract 不再包含 `variants`、`variant_versions`、`tag_sets`。
- schema contract 包含 `skill_versions`、`skills.current_version_id`、`eval_runs.skill_version_id/environment_tags/run_context/run_context_hash`。
- 创建 Skill 后有 `current_version` 和 `versions`。
- 上传 SkillVersion 后版本线增加，`make_current` 生效。
- 记录 EvalRun 必须绑定 `skill_version_id + eval_set_version_id`。
- 记录 EvalRun 保存 actual output artifact 和 environment tags/context。
- History 返回 skill_version 和 run context，不返回 variant。
- Bundle diff 使用两个 skill version id。
- Accepted verification 按 `skill_version_id + eval_set_version_id + run_context_hash` 唯一。

Web：

- Hub / 概览 / 版本 / 测评 / 历史不出现用户可见 Variant 文案。
- 新建 Skill 不再要求 tags。
- 上传版本不再要求 tags。
- 测评页必须能输入运行环境标签。
- 历史页显示运行环境标签和 actual vs expected。
- E2E 覆盖新建 Skill、上传 SkillVersion、后端 diff、输入环境标签并记录 EvalRun、历史证据链。
- 视觉和 320px 小窗口 smoke 更新。

文档：

- README 改成 SkillVersion / EvalRun context 模型。
- API contract 和 architecture 文档同步。
- 新增正式审计说明旧 Variant 去除范围和验证结果。

## 9. 验收条件

- 代码中用户可见正式版路径不再出现 Variant/VariantVersion 作为产品概念。
- API 主契约使用 `skill_version_id`，不要求 `variant_version_id`。
- 运行环境标签只存放在 `EvalRun` 相关字段。
- 刷新或重启后 Skill、SkillVersion、EvalRun、history 数据仍持久化。
- Bundle diff 有真实后端数据并比较两个 SkillVersion。
- Run eval 能输入 actual output 和 environment tags/context。
- 历史页能看到 SkillVersion、EvalSetVersion、environment tags/context、actual vs expected。
- `uv run pytest`、`npm run test`、`npm run lint`、`npm run build`、`npm run e2e`、`npm run e2e:visual`、agent-browser 实操和 main CI 通过。
