# 前端依赖接口清单

本文档列出 `apps/web` 前端实际调用的所有后端 API 接口，来源为 `apps/web/src/lib/api.ts`。

## 基地址解析

前端通过以下规则推导 API 基地址：

1. 优先使用环境变量 `VITE_SKILLHUB_API_URL`（完整 URL）。
2. 否则使用 `VITE_SKILLHUB_API_PORT`（默认 `8000`）拼接当前浏览器的 `protocol + hostname`。

---

## 查询接口（GET）

### 1. 获取当前会话

```
GET /api/session
```

**响应** `SessionInfo`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `actor` | `string` | 当前操作者标识 |
| `subject_type` | `string` | 主体类型 |

---

### 2. Skill 列表

```
GET /api/skills
```

**响应** `SkillSummary[]`：每个元素包含 `skill`（基础信息）和 `summary`（当前版本、测评集、最近测评运行等聚合摘要）。

---

### 3. Skill 详情

```
GET /api/skills/{skill_id}
```

**响应** `SkillDetail`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `skill` | `SkillRecord` | Skill 基础信息 |
| `summary` | `SkillSummary.summary` | 聚合摘要 |
| `versions` | `SkillVersion[]` | 全部不可变版本 |
| `eval_sets` | `EvalSetSummary[]` | 测评集列表 |
| `latest_eval_runs` | `EvalRunRecord[]` | 最近测评运行 |
| `role_assignments` | `unknown[]` | 角色授权 |
| `audit_events` | `unknown[]` | 审计事件 |

---

### 4. 测评集版本详情

```
GET /api/eval-set-versions/{version_id}
```

**响应** `EvalSetVersionDetail`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `eval_set_version` | `EvalSetVersion` | 版本信息 |
| `eval_set` | `EvalSetSummary`（去除 `current_version` 和 `versions`） | 所属测评集 |
| `cases` | `EvalSetCase[]` | 该版本包含的所有 case 及其 case version |

---

### 5. 测评用例历史版本

```
GET /api/eval-cases/{case_id}/versions
```

**响应** `EvalCaseHistory`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `case` | `EvalSetCase.case` | case 基础信息 |
| `versions` | `Array<{ case_version, included_in_eval_set_versions }>` | 所有历史 case version 及其所属的测评集版本 |

---

### 6. 测评运行历史

```
GET /api/skills/{skill_id}/eval-runs
```

**响应** `EvalRunHistory`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `skill` | `SkillRecord` | Skill 基础信息 |
| `runs` | `EvalRunContext[]` | 运行列表，每条包含 `eval_run`、`skill_version`、`eval_set`、`eval_set_version` |

---

### 7. 测评运行详情

```
GET /api/eval-runs/{run_id}
```

**响应** `EvalRunDetail`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `eval_run` | `EvalRunRecord` | 运行记录 |
| `skill` | `SkillRecord` | Skill 基础信息 |
| `skill_version` | `SkillVersion` | 对应的 Skill 版本 |
| `eval_set_version` | `EvalSetVersion` | 对应的测评集版本 |
| `case_results` | `Array<{ position, result, result_artifact, case, case_version }>` | 逐条 case 结果、actual output artifact 和 expected output 对照 |

---

### 8. Bundle Diff

```
GET /api/artifacts/diff?left_skill_version_id={id}&right_skill_version_id={id}
```

**响应** `BundleDiff`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `left` / `right` | `{ skill_version_id, version_number, content_digest }` | 两端版本信息 |
| `summary` | `{ added, changed, removed, unchanged, binary }` | 文件变更统计 |
| `files` | `BundleDiffFile[]` | 逐文件的 status、digest、size 和 hunks（行级 diff） |

---

## 写入接口（POST / PATCH）

### 9. 导入 Skill

```
POST /api/skill-imports
Content-Type: application/json
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `owner_ref` | `string` | 是 | 维护者标识 |
| `source` | `BundleSource` | 是 | bundle 来源（`files` 或 `zip` 两种形式） |
| `display_name` | `string` | 否 | 版本显示名称 |

`BundleSource` 为联合类型：
- `{ kind: "files", name, files: [{ path, content_text?, content_base64? }] }` — 文件夹上传
- `{ kind: "zip", name, zip_base64 }` — zip 上传

**响应** `{ skill_id: string, skill_version_id: string }`

---

### 10. 创建 Skill 版本

```
POST /api/skill-versions
Content-Type: application/json
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `skill_id` | `string` | 是 | 所属 Skill |
| `source` | `BundleSource` | 是 | bundle 来源 |
| `make_current` | `boolean` | 否 | 是否设为当前版本 |
| `display_name` | `string` | 否 | 版本显示名称 |

**响应** `{ skill_version_id: string }`

---

### 11. 更新 Skill 版本名称

```
PATCH /api/skill-versions/{version_id}
Content-Type: application/json
```

**请求体**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `display_name` | `string \| null` | 新的显示名称，传 `null` 清除 |

---

### 12. 更新测评集版本名称

```
PATCH /api/eval-set-versions/{version_id}
Content-Type: application/json
```

**请求体**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `display_name` | `string \| null` | 新的显示名称，传 `null` 清除 |

---

### 13. 创建测评用例

```
POST /api/eval-cases
Content-Type: application/json
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `skill_id` | `string` | 是 | 所属 Skill |
| `title` | `string` | 是 | 用例标题（1-160 字符） |
| `input_text` | `string` | 是 | 输入文本（1-20000 字符） |
| `expected_output` | `string` | 是 | 期望输出（1-10000 字符） |
| `notes` | `string` | 否 | 备注（最多 2000 字符） |
| `eval_set_version_display_name` | `string` | 否 | 若产生新的测评集版本，其显示名称 |

**响应** `EvalCaseMutationResult`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `skill_id` | `string` | 所属 Skill |
| `eval_set_id` | `string` | 所属测评集 |
| `eval_set_version_id` | `string` | 当前/新建的测评集版本 |
| `eval_case_id` | `string` | case ID |
| `eval_case_version_id` | `string` | 新建的 case version ID |

---

### 14. 编辑测评用例

```
PATCH /api/eval-cases/{case_id}
Content-Type: application/json
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `case_id` | `string` | 是 | 要编辑的 case ID（同时放入 body） |
| `title` | `string` | 是 | 标题 |
| `input_text` | `string` | 是 | 输入文本 |
| `expected_output` | `string` | 是 | 期望输出 |
| `notes` | `string` | 否 | 备注 |
| `make_current` | `boolean` | 是 | 是否将新 case version 设为当前 |
| `eval_set_version_display_name` | `string` | 否 | 若产生新的测评集版本，其显示名称 |

**响应** `EvalCaseMutationResult`（同上）

---

### 15. 记录测评运行

```
POST /api/eval-runs
Content-Type: application/json
```

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `skill_version_id` | `string` | 是 | 对应的 Skill 版本 |
| `eval_set_version_id` | `string` | 是 | 对应的测评集版本 |
| `strategy` | `string` | 是 | 测评策略（如 `manual_pass_fail`） |
| `environment_tags` | `string[]` | 是 | 运行环境标签 |
| `run_context` | `Record<string, unknown>` | 是 | 运行环境上下文 |
| `results` | `Record<string, ManualEvalResultPayload>` | 是 | 每个 case version ID 对应的 `{ passed, actual_output }` |

**响应** `{ eval_run_id: string }`

---

## 错误响应格式

所有接口在非 2xx 时返回：

```json
{
  "detail": "错误描述",
  "field_errors": { "field_name": "字段错误信息" }
}
```

`field_errors` 可能是对象或数组形式，前端会统一归一化处理。
