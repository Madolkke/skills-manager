# SkillHub API Contract

本文档描述当前正式版 API。核心模型为 `Skill -> SkillVersion -> EvalRun(context) + EvalSetVersion`。

## 核心对象

| 对象 | 语义 |
| --- | --- |
| `Skill` | 稳定入口，保存 slug、owner、lifecycle 和 `current_version_id`。 |
| `SkillVersion` | 不可变 Skill bundle 内容快照，同一 Skill 内 `version` 使用 SemVer 且唯一。 |
| `EvalCaseVersion` | 不可变测试用例快照，保存 input、expected output 和 notes。 |
| `EvalSetVersion` | case version 列表快照；未被 `EvalRun` 使用的当前版本可作为工作版更新，已有运行记录后变为历史快照。 |
| `EvalRun` | 一次 exact `SkillVersion + EvalSetVersion + run_context` 的测评事实。 |
| `CaseResult` | 某次 run 中某个 case version 的 pass/fail 和 actual output。 |
| `AcceptedVerification` | 把一次 finished run 接受为当前上下文验证依据。 |
| `RoleAssignment` | Skill 作用域授权。 |
| `AuditEvent` | append-only 治理事实。 |

## 关键字段

### `Skill`

- `id`
- `slug`
- `owner_ref`
- `current_version_id`
- `lifecycle_status`
- `created_at`
- `updated_at`

### `SkillVersion`

- `id`
- `skill_id`
- `version`：SemVer，例如 `1.0.0`、`1.2.3-beta.1` 或 `1.2.3+build.5`
- `version_number`
- `content_ref`
- `content_digest`
- `change_summary`
- `bundle_artifact`
- `bundle_files`
- `created_at`
- `created_by`

`version_number` 仅作为历史兼容和创建顺序号保留；产品展示、创建新版本和 API 使用方应以 `version` 为准。
创建初始 SkillVersion 时可传 `version`，不传默认 `0.0.1`。追加版本时可传目标 SemVer，不传时后端自动增加 patch。

### `EvalRun`

- `id`
- `skill_id`
- `skill_version_id`
- `eval_set_version_id`
- `strategy`
- `status`
- `environment_tags`
- `run_context`
- `run_context_hash`
- `summary`
- `result_artifact_id`
- `created_at`
- `created_by`

## Actor Context

所有 mutation endpoint 的操作者身份来自请求级 actor context：

1. `skillhub_actor` HttpOnly cookie，后端 HMAC 签名。
2. `X-SkillHub-Actor` header。
3. 默认本地 actor：`product-operator`。

签名 cookie 无效时返回 `400 Invalid actor session.`，不会回退到默认 actor。

## 权限

| Permission | 条件 | 用途 |
| --- | --- | --- |
| `role.manage` | `owner` | 管理 skill role assignment。 |
| `verification.accept` | `owner` 或 `maintainer` | 接受一次 EvalRun 为验证依据。 |

## 字段校验

| 字段 | 规则 |
| --- | --- |
| `slug` | 小写字母、数字、连字符，最多 64 字符，必须以字母或数字开头。 |
| `owner_ref` / actor | 字母、数字、点、下划线、`@`、连字符，最多 120 字符。 |
| `environment_tags[]` | 字母、数字、点、下划线、连字符，每个最多 64 字符。 |
| `change_summary` | 1-1000 字符。 |
| Eval case `title` | 1-160 字符。 |
| Eval case `input_text` | 1-20000 字符。 |
| Eval case `expected_output` | 1-10000 字符。 |
| Eval case `notes` | 可空，最多 2000 字符。 |
| Actual output | 可空，最多 20000 字符。 |
| Saved view `name` | 1-80 字符，同一 skill + view type 下唯一。 |
| Accepted verification `note` | 可空，最多 1000 字符。 |

错误响应包含 `detail`，可定位字段时额外返回 `field_errors`。

## 查询接口

| Endpoint | 返回 |
| --- | --- |
| `GET /health` | 健康状态。 |
| `GET /api/session` | 当前 actor。 |
| `GET /api/skills` | Hub Skill 摘要列表。 |
| `GET /api/skills/{skill_id}` | Skill 详情、versions、eval sets、latest runs、roles、audit events。 |
| `GET /api/skills/{skill_id}/capabilities` | 当前 actor 在该 Skill 上的 permissions。 |
| `GET /api/skills/{skill_id}/role-assignments` | Skill role assignments。 |
| `GET /api/skills/{skill_id}/audit-events` | Skill 审计事件。 |
| `GET /api/eval-set-versions/{version_id}` | EvalSetVersion 和 case versions。 |
| `GET /api/skills/{skill_id}/eval-runs` | EvalRun 历史列表。 |
| `GET /api/skills/{skill_id}/eval-run-matrix` | Run matrix read model。 |
| `GET /api/eval-runs/{run_id}` | EvalRun 详情和逐 case result。 |
| `GET /api/eval-runs/compare` | 两个 finished run 的修复/回退比较。 |
| `GET /api/eval-cases/{case_id}/versions` | 某个 case 的历史版本。 |
| `GET /api/artifacts/diff` | 两个 SkillVersion bundle 的真实 diff。 |
| `GET /api/skills/{skill_id}/saved-views` | Saved view 列表。 |

## 写入接口

| Endpoint | 行为 |
| --- | --- |
| `POST /api/session` | 使用本地 access code 设置 actor cookie。 |
| `DELETE /api/session` | 清除 actor cookie。 |
| `POST /api/skills` | 创建 Skill、初始 SkillVersion、Primary EvalSet 和 owner role。 |
| `POST /api/skill-imports` | 从标准 Skill bundle 导入 Skill。 |
| `POST /api/skill-versions` | 创建不可变 SkillVersion，可选择 `make_current`。 |
| `PATCH /api/skills/{skill_id}` | 更新 slug 和 owner。 |
| `DELETE /api/skills/{skill_id}` | 归档 Skill。 |
| `POST /api/skills/{skill_id}/role-assignments` | 添加 role assignment。 |
| `DELETE /api/role-assignments/{id}` | 撤销 role assignment。 |
| `POST /api/eval-cases` | 创建 case 和 case version；当前 EvalSetVersion 无运行记录时原地更新，有运行记录时创建新快照。 |
| `POST /api/eval-cases/batch` | 批量创建 case；同样遵循当前 EvalSetVersion 的工作版/已锁定规则。 |
| `POST /api/eval-case-versions` | 创建新的 case version；必要时创建新 EvalSetVersion。 |
| `PATCH /api/eval-cases/{case_id}` | 编辑 case 并生成新的 case version。 |
| `POST /api/eval-cases/{case_id}/restores` | 从历史 case version 恢复。 |
| `DELETE /api/eval-cases/{case_id}` | 归档 case。 |
| `POST /api/eval-runs` | 记录手工 pass/fail run、运行环境和 actual output。 |
| `POST /api/eval-runs/accepted-verifications` | 接受一次 finished run 为验证依据。 |
| `POST /api/saved-views` | 保存历史或 matrix 视图配置。 |
| `DELETE /api/saved-views/{id}` | 删除 saved view。 |

## EvalRun 写入约束

`POST /api/eval-runs` 请求体核心字段：

```json
{
  "skill_version_id": "skillver_...",
  "eval_set_version_id": "evalsetver_...",
  "strategy": "manual_pass_fail",
  "environment_tags": ["windows", "codex"],
  "run_context": { "os": "windows", "runner": "local", "model": "gpt-5" },
  "results": {
    "casever_...": { "passed": true, "actual_output": "实际运行结果" }
  }
}
```

约束：

- `skill_version_id` 和 `eval_set_version_id` 必须属于同一个 Skill。
- `results` 必须和目标 `EvalSetVersion` 的 case version 集合完全一致。
- actual output 非空时写入 `actual_output` artifact。
- `environment_tags + run_context` 会生成稳定 `run_context_hash`。

## 持久化

- API 只接受 PostgreSQL 连接串，必须通过 `SKILLHUB_DATABASE_URL` 注入。
- 支持 `postgresql://` 和 `postgresql+psycopg://` 两类 SQLAlchemy URL。
- 应用启动时通过 SQLAlchemy metadata 创建当前 schema；测试使用 `SKILLHUB_TEST_DATABASE_URL` 指向隔离测试库。
