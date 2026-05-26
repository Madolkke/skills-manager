# SkillHub API Contract

这份文档描述当前正式版 API 契约。当前模型已经收束为 `Skill -> SkillVersion -> EvalRun(context) + EvalSetVersion`，运行环境标签属于每一次 `EvalRun`，不属于内容版本。

## 核心对象

- `Skill` 是稳定入口，负责 slug、owner、生命周期和当前内容版本指针。
- `SkillVersion` 是不可变 Skill bundle 内容快照，按同一 Skill 内的 `version_number` 递增。
- `EvalCase` 是稳定测试场景入口。
- `EvalCaseVersion` 是不可变测试用例快照：`input + expected_output + notes`。
- `EvalSetVersion` 是不可变 case version 列表快照。
- `EvalRun` 必须绑定 exact `SkillVersion + EvalSetVersion`，并保存 `environment_tags`、`run_context`、`run_context_hash`、summary 和 case result。
- `CaseResult` 是某个 case version 在某次 run 中的最终 `pass/fail`，可关联 actual output artifact。
- `AcceptedVerification` 把某个 `SkillVersion + EvalSetVersion + run_context_hash` 指向一次 finished `EvalRun`。
- `RoleAssignment` 是 skill 作用域授权，保护 accepted verification 和角色管理等高风险动作。
- `AuditEvent` 是 append-only 治理事实。

## 字段概要

### Skill

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 内部唯一 ID。 |
| `slug` | string | Hub 展示和搜索用稳定名称。 |
| `owner_ref` | string | 所有者引用。真实动作权限由 `RoleAssignment` 判定。 |
| `current_version_id` | string \| null | 当前 Skill 内容版本。 |
| `lifecycle_status` | enum | `active` 或 `archived`。 |
| `created_at` / `updated_at` | ISO datetime | 创建和更新时间。 |

### SkillVersion

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 内部唯一 ID。 |
| `skill_id` | string | 所属 `Skill.id`。 |
| `version_number` | integer | 同一 Skill 内递增，从 1 开始。 |
| `content_ref` | object | 不可变内容位置和 digest。 |
| `content_digest` | string | 内容摘要。 |
| `change_summary` | string | 本次内容更新说明。 |
| `bundle_artifact` | object \| null | 标准 Skill bundle artifact。 |
| `bundle_files` | array | 可预览文件树。 |
| `created_at` / `created_by` | string | 创建事实。 |

### EvalRun

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 内部唯一 ID。 |
| `skill_id` | string | 所属 Skill。 |
| `skill_version_id` | string | 被测不可变内容版本。 |
| `eval_set_version_id` | string | 使用的测评集快照。 |
| `strategy` | string | 当前手工流程使用 `manual_pass_fail`。 |
| `status` | enum | `queued`、`running`、`finished`、`failed`。 |
| `environment_tags` | string[] | 运行环境标签，例如 `windows`、`codex`、`ci`。 |
| `run_context` | object | 结构化环境上下文，例如 `{ "os": "windows", "runner": "local", "model": "gpt-5" }`。 |
| `run_context_hash` | string | `environment_tags + run_context` 的规范化 hash。 |
| `summary` | object | `{ passed, failed, total }`。 |
| `result_artifact_id` | string \| null | run 级 artifact，当前手工流程通常为空。 |
| `created_at` / `created_by` | string | 创建事实。 |

### RoleAssignment 与权限

当前 permission key：

| Permission | true 条件 | 用途 |
| --- | --- | --- |
| `role.manage` | `owner` | 添加或撤销 skill role assignment。 |
| `verification.accept` | `owner` 或 `maintainer` | 接受某次 run 为验证依据。 |

角色到动作：

| 动作 | 需要角色 |
| --- | --- |
| 管理 skill role assignment | `owner` |
| `POST /api/eval-runs/accepted-verifications` | `owner` 或 `maintainer` |
| `DELETE /api/skills/{skill_id}` | `owner` |

### Actor Context

所有 mutation endpoint 的操作者身份来自请求级 actor context，而不是 JSON body。读取优先级：

1. `skillhub_actor` HttpOnly cookie，值由后端 HMAC 签名。
2. `X-SkillHub-Actor` header，用于直接 API 调用和自动化脚本。
3. 缺省本地 actor：`product-operator`。

如果 cookie 存在但签名无效，后端返回 `400 Invalid actor session.`，不会回退到默认 actor。

## Error Response

错误响应保留 `detail` 字段；当错误可以定位到请求字段时，额外返回 `field_errors`。

```json
{
  "detail": "Skill ID 已存在：code-reviewer",
  "field_errors": [
    {
      "field": "slug",
      "message": "Skill ID 已存在：code-reviewer",
      "code": "skill.slug_conflict"
    }
  ]
}
```

当前基础格式规则：

| 字段 | 规则 | 错误字段 |
| --- | --- | --- |
| `slug` | `^[a-z0-9][a-z0-9-]{0,63}$`，最多 64 字符。 | `slug` |
| `owner_ref` / actor | 1-120 字符，只能使用字母、数字、点、下划线、`@` 和连字符。 | `owner_ref` / `actor` |
| `environment_tags[]` | 每个 tag 1-64 字符，只能使用字母、数字、`.`、`_`、`-`。 | `environment_tags` |
| `change_summary` | 1-1000 字符。 | `change_summary` |
| Eval case `title` | 1-160 字符。 | `title` 或 `cases[n].title` |
| Eval case `input_text` | 1-20000 字符。 | `input_text` 或 `cases[n].input_text` |
| Eval case `expected_output` | 1-10000 字符。 | `expected_output` 或 `cases[n].expected_output` |
| Eval case `notes` | 可空；最多 2000 字符。 | `notes` 或 `cases[n].notes` |
| Actual output | 可空；最多 20000 字符。 | `results.{case_version_id}.actual_output` |
| Saved view `name` | 1-80 字符；trim 后不能为空，同一 skill + view type 下不能重复。 | `name` |
| Accepted verification `note` | 可空；最多 1000 字符。 | `note` |

## 查询接口

### Health

```http
GET /health
```

### Session

```http
GET /api/session
POST /api/session
DELETE /api/session
```

`POST /api/session` 请求体：

```json
{
  "actor": "release-manager",
  "access_code": "skillhub-dev"
}
```

### Skill 列表

```http
GET /api/skills
```

返回 `SkillSummary[]`：

```json
[
  {
    "skill": { "id": "skill_...", "slug": "code-reviewer", "owner_ref": "product-operator" },
    "summary": {
      "skill": { "id": "skill_...", "slug": "code-reviewer" },
      "current_version": { "id": "skillver_...", "version_number": 2 },
      "primary_eval_set": { "id": "evalset_...", "current_version_id": "evalsetver_..." },
      "latest_accepted_eval_run": { "id": "evalrun_...", "summary": { "passed": 3, "failed": 0, "total": 3 } }
    }
  }
]
```

### Skill 详情

```http
GET /api/skills/{skill_id}
```

返回：

- `skill`
- `summary`
- `versions: SkillVersion[]`
- `eval_sets`
- `latest_eval_runs`
- `role_assignments`
- `audit_events`

### EvalSetVersion 详情

```http
GET /api/eval-set-versions/{eval_set_version_id}
```

返回测评集快照和其包含的 case version 列表。

### EvalRun 历史

```http
GET /api/skills/{skill_id}/eval-runs?skill_version_id=&eval_set_version_id=&strategy=&status=&limit=
GET /api/skills/{skill_id}/eval-run-matrix?skill_version_id=&eval_set_version_id=&strategy=&status=&limit=
GET /api/eval-runs/{eval_run_id}
GET /api/eval-runs/compare?baseline_run_id=&candidate_run_id=
```

历史和矩阵查询都返回 `skill_version`、`eval_set_version`、`eval_run` 和 accepted verification 上下文。详情接口额外返回逐 case result、actual output artifact、case version、input artifact 和 expected output artifact。

### Bundle Diff

```http
GET /api/artifacts/diff?left_skill_version_id={left}&right_skill_version_id={right}
```

两个 `skill_version_id` 必须属于同一个 Skill。返回：

- `left` / `right`：版本号和 digest。
- `summary`：新增、变更、删除、未变更、二进制文件数量。
- `files`：每个文件的状态、digest、大小和首段 hunk。

## 写入接口

### 创建 Skill

```http
POST /api/skills
```

```json
{
  "slug": "code-reviewer",
  "owner_ref": "product-operator",
  "content_ref": { "kind": "inline", "locator": "seed://code-reviewer", "digest": "sha256:..." },
  "change_summary": "Initial bundle"
}
```

行为：

- 创建 `Skill`。
- 创建 `SkillVersion v1`。
- 设置 `Skill.current_version_id`。
- 创建 Primary `EvalSet` 和 `EvalSetVersion v1`。
- 创建 owner role assignment。

### 导入标准 Skill bundle

```http
POST /api/skill-imports
```

```json
{
  "owner_ref": "product-operator",
  "source": {
    "kind": "files",
    "name": "code-reviewer",
    "files": [
      {
        "path": "code-reviewer/SKILL.md",
        "content_text": "---\nname: code-reviewer\ndescription: Review pull requests.\n---\n# Code Reviewer\n"
      }
    ]
  }
}
```

成功后返回 `skill_id`、`skill_version_id`、`eval_set_id`、`eval_set_version_id` 和 `version_number`。

### 创建 SkillVersion

```http
POST /api/skill-versions
```

```json
{
  "skill_id": "skill_...",
  "source": {
    "kind": "files",
    "name": "code-reviewer",
    "files": []
  },
  "make_current": true
}
```

行为：

- 保存不可变 bundle artifact。
- 创建新的 `SkillVersion`。
- `make_current=true` 时移动 `Skill.current_version_id`。

### 更新或归档 Skill

```http
PATCH /api/skills/{skill_id}
DELETE /api/skills/{skill_id}
```

`PATCH` 可更新 `slug`、`owner_ref`、`current_version_id`。`current_version_id` 必须属于同一个 Skill。

### 管理 EvalCase

```http
POST /api/eval-cases
POST /api/eval-cases/batch
POST /api/eval-case-versions
PATCH /api/eval-cases/{case_id}
POST /api/eval-cases/{case_id}/restores
DELETE /api/eval-cases/{case_id}
```

新增、编辑、恢复或归档 case 都会维护 case version 与当前 Primary `EvalSetVersion`，保证历史 run 不被覆盖。

### 记录 EvalRun

```http
POST /api/eval-runs
```

```json
{
  "skill_version_id": "skillver_...",
  "eval_set_version_id": "evalsetver_...",
  "strategy": "manual_pass_fail",
  "environment_tags": ["codex", "windows"],
  "run_context": {
    "os": "windows",
    "runner": "local",
    "model": "gpt-5"
  },
  "results": {
    "casever_...": {
      "passed": true,
      "actual_output": "实际运行结果文本"
    }
  }
}
```

约束：

- `skill_version_id` 和 `eval_set_version_id` 必须属于同一个 Skill。
- `results` 必须和该 `EvalSetVersion` 的 case version 集合完全一致，不能缺失或多传。
- `results` 兼容旧布尔值，但正式前端应发送 `{ passed, actual_output }`。
- actual output 非空时写入 `actual_output` artifact，并在历史页展示 actual vs expected。

### 接受验证

```http
POST /api/eval-runs/accepted-verifications
```

```json
{
  "eval_run_id": "evalrun_...",
  "note": "本环境验证通过"
}
```

行为：

- 只能接受 `finished` run。
- 唯一键为 `(skill_id, skill_version_id, eval_set_version_id, run_context_hash)`。
- 同一上下文重复接受会更新指针，不修改旧 run。

### Saved Views

```http
GET /api/skills/{skill_id}/saved-views
POST /api/saved-views
DELETE /api/saved-views/{saved_view_id}
```

`config` 当前允许 `skill_version_id`、`eval_set_version_id`、`strategy` 和 `status`，未知字段会被忽略。

## 持久化与迁移

- 默认本地连接由 `SKILLHUB_DATA_DIR` 派生，落到 `.data/skillhub.sqlite3`。
- 干净 clone 后无需手动创建 SQLite 文件；API 启动会创建 schema。
- Windows Git Bash 默认启动不会使用 `sqlite:///:memory:`。
- 在线迁移会把旧内容版本复制到 `skill_versions`，把历史运行环境标签迁移到 `eval_runs.environment_tags`，并为 run 生成 `run_context_hash`。
