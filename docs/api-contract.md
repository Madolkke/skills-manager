# SkillHub API Contract

本文档描述当前正式版 API。核心模型为 `Skill -> SkillVersion -> EvalRun(context) + EvalSetVersion`。

## 核心对象

| 对象 | 语义 |
| --- | --- |
| `Skill` | 稳定入口，保存不可变内部 `id`、可重命名 slug、可选中文名、owner、lifecycle 和 `current_version_id`。 |
| `SkillVersion` | 不可变 Skill bundle 内容快照，同一 Skill 内 `version` 使用 SemVer 且唯一。 |
| `EvalCaseVersion` | 不可变测试用例快照，保存 input、expected output 和 notes。 |
| `EvalSetVersion` | case version 列表快照；未被 `EvalRun` 使用的当前版本可作为工作版更新，已有运行记录后变为历史快照。 |
| `EvalRun` | 一次 exact `SkillVersion + EvalSetVersion + run_context` 的测评事实。 |
| `CaseResult` | 某次 run 中某个 case version 的 pass/fail 和 actual output。 |
| `AcceptedVerification` | 把一次 finished run 接受为当前上下文验证依据。 |
| `RoleAssignment` | 单个 Skill、Skill Tag 或全部 Skill 作用域授权。 |
| `AuditEvent` | append-only 治理事实。 |
| `Workflow` | 与 Skill 永久一对一绑定的最新作者文档。 |
| `WorkflowSync` | 某个 Workflow revision 生成 SkillVersion 时的精确源快照和追溯记录。 |
| `CollectionDefinition` | 全局共享采集定义；同一 ID 下 revision 不可变。 |
| `WorkflowDebugCase` | 绑定写作侧 Step 的非版本化单步调试输入、采集 fixture 和预期直接目标。 |
| `WorkflowDebugRun` | 单次调试的案例快照、Workflow 证据、执行器状态和命中判定。 |

## 关键字段

### `Skill`

- `id`
- `slug`：用户可见且全局唯一的“Skill ID”，允许重命名。
- `display_name`：可选中文名，去除首尾空白后最长 120 字符，不要求唯一。
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
- `description`：从该版本 Skill 内容 Artifact manifest 的 `metadata.description` 派生；无法读取时为 `null`。
- `change_summary`
- `bundle_artifact`
- `bundle_files`
- `created_at`
- `created_by`
- `workflow_sync`：如果该版本由 Workflow 生成，返回 `workflow_id/workflow_revision/generator_version/created_at`。

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
| `role.manage` | `owner` 或 `admin` | 管理 skill role assignment。 |
| `skill.delete` | `owner` 或 `admin` | 永久删除 Skill。 |
| `verification.accept` | `owner` 或 `maintainer` | 接受一次 EvalRun 为验证依据。 |
| `skill.edit` | `owner`、`maintainer` 或 `admin` | 保存 Workflow、维护调试例以及读取和推进单步调试运行。 |
| `skill.version.create` | `owner`、`maintainer` 或 `admin` | 同步 Workflow 或重新激活其生成版本。 |

## 字段校验

| 字段 | 规则 |
| --- | --- |
| `slug` | 小写字母、数字、连字符，最多 64 字符，必须以字母或数字开头。 |
| `display_name` | 可空；去除首尾空白后最长 120 字符，空白值保存为 `null`。 |
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
| `GET /api/skills` | Hub Skill 摘要列表，`summary` 额外投影当前版本的 `review_status` 和 `publish_status`。 |
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
| `GET /api/skills/{skill_id}/workflow` | Workflow 当前文档、revision、校验、同步状态、保存信息和 capabilities。 |
| `GET /api/skills/{skill_id}/workflow/formatted` | 返回当前 Workflow document 的特定格式表示；当前转换为原样透传。 |
| `GET /api/skills/{skill_id}/workflow/executor` | 将当前保存的写作侧 Workflow 转换为执行器 Workflow 定义；详见[执行器 Workflow 转换接口](executor-workflow-api.md)。 |
| `GET /api/workflow-log-schema` | 返回 Workflow schema v5 日志 SQL 使用的 DuckDB 方言、`logs`/`params` 表名和固定列目录。 |

配置匹配 Collection 的结构、表达式路径和执行边界见[Workflow 配置匹配 Collection](workflow-config-matching.md)。SkillHub 不读取配置文本或执行匹配。
| `GET /api/skills/{skill_id}/workflow/collections` | 全局 Collection Catalog 最新 revisions。 |
| `GET /api/skills/{skill_id}/workflow/debug-cases` | 当前 actor 可编辑的 Workflow 调试例。 |
| `GET /api/workflow-debug-cases/{case_id}` | 单个 Workflow 调试例。 |
| `GET /api/workflow-debug-cases/{case_id}/runs` | 调试运行历史，使用 cursor 分页。 |
| `GET /api/workflow-debug-runs/{run_id}` | 当前持久化的调试运行状态，不推进执行器。 |

## 写入接口

| Endpoint | 行为 |
| --- | --- |
| `POST /api/session` | 使用本地 access code 设置 actor cookie。 |
| `DELETE /api/session` | 清除 actor cookie。 |
| `POST /api/skills` | 创建 Skill、初始 SkillVersion、Primary EvalSet 和 owner role。 |
| `POST /api/skill-imports` | 从标准 Skill bundle 导入 Skill。 |
| `POST /api/skill-versions` | 创建不可变 SkillVersion，可选择 `make_current`。 |
| `PATCH /api/skills/{skill_id}` | 更新 slug、中文名、owner 和 Tag；重命名 slug 时自动创建下一个 Patch 版本。 |
| `DELETE /api/skills/{skill_id}` | 永久删除 Skill 及其从属数据；请求体必须提供精确匹配的 `confirmation_slug`。 |
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
| `POST /api/workflows` | 原子创建 Workflow Skill、`0.0.1` 空白版本、Primary EvalSet、角色、Tag 和 Workflow revision 1。 |
| `PUT /api/skills/{skill_id}/workflow` | 显式保存 Workflow 文档和本次 CollectionChanges。 |
| `POST /api/skills/{skill_id}/workflow/import` | 使用专用 Import Bundle 覆盖 Workflow，并为全部导入 Collection 创建独立身份。 |
| `GET /api/skills/{skill_id}/workflow/export` | 将当前已保存 Workflow 导出为可移植 Import Bundle。 |
| `PATCH /api/skills/{skill_id}/workflow/metadata` | 显式保存 Workflow 元信息。 |
| `GET /api/workflow-skill-generators` | 返回内置 Generator descriptor 和服务端默认项。 |
| `POST /api/skills/{skill_id}/workflow/sync-preview` | 无写入地生成 Bundle、当前版本文本 diff、预计动作和确认摘要。 |
| `POST /api/skills/{skill_id}/workflow/sync` | 重新生成并校验已确认预览，再创建或重新激活 SkillVersion。 |
| `POST /api/skills/{skill_id}/workflow/debug-cases` | 创建绑定 Step 的非版本化调试例。 |
| `PATCH /api/workflow-debug-cases/{case_id}` | 最后写入覆盖更新调试例。 |
| `DELETE /api/workflow-debug-cases/{case_id}` | 无活动运行时删除调试例并级联删除历史。 |
| `POST /api/workflow-debug-cases/{case_id}/runs` | 基于当前已保存 Workflow 启动或复用活动单步调试运行。 |
| `POST /api/workflow-debug-runs/{run_id}/advance` | 查询一次执行器状态，并按需自动恢复一次暂停。 |

`DELETE /api/skills/{skill_id}` 是破坏性接口，已替换旧版归档语义。仅 owner 或 admin 可调用：

```json
{
  "confirmation_slug": "example-skill"
}
```

确认 slug 区分大小写且不会自动修正。缺少请求体返回 `422`，确认不匹配返回 `400` 和 `skill.delete_confirmation_mismatch`，权限不足返回 `403`；存在排队中或运行中的测评、发布或关联 Job 时返回 `409`。成功返回 `{"ok": true}`。

重命名使用稳定内部 `skill_id` 定位 Skill，并通过 `expected_slug` 防止覆盖并发修改：

```json
{
  "slug": "renamed-skill",
  "expected_slug": "example-skill",
  "display_name": "示例技能",
  "owner_ref": "owner"
}
```

slug 变化时，后端会复制当前不可变 Skill 内容，只更新 manifest 与根目录 `SKILL.md` 的 `name`，创建下一个 Patch SemVer 并设为当前版本。历史版本不会修改。存在活动任务、当前版本不是有效 Artifact Bundle、slug 重复或 `expected_slug` 已过期时返回 `409`，整个更新回滚。只修改 `display_name` 不会创建版本。

`GET /api/skills` 的状态字段只关联 `current_version_id`：`review_status` 为 `unreviewed`、`open`、`closed` 或 `cancelled`；`publish_status` 为 `unpublished`、`pending`、`releasing`、`released`、`failed` 或 `cancelled`。同一当前版本存在多个发布目标时，任一目标为 `released` 即汇总为 `released`；否则依次优先 `releasing`、待处理、`failed`、`cancelled`。历史版本记录不会影响该摘要。

评审页支持站内定位链接：`/skills?section=skills&skill=<skill_id>&tab=reviews&review=<review_id>`。链接仅携带资源标识，不授予额外权限；客户端会定位并高亮对应记录。

后台通用角色接口支持下列固定的全局 Skill admin 授权；其他 `global` 组合会被数据库约束拒绝：

```json
{
  "subject_type": "user",
  "subject_id": "alice",
  "resource_type": "global",
  "resource_id": "skills",
  "role": "admin"
}
```

该授权对全部当前及未来 Skill 生效，但不能代替 `SKILLHUB_ADMIN_CONSOLE_KEY`，也不会开放 `/api/admin/*`。

## Workflow 接口约束

CLI Collection 可选返回 `spec.commandParameterSyntax: "angle-v1"`。启用后，`commandTemplate` 中每个 `<name>` 必须对应唯一同名输入；无效尖括号语法和缺失输入作为 Workflow validation error 返回。字段缺失表示历史兼容模式，读取和未修改保存不会自动启用。

`GET /api/skills/{skill_id}/workflow/formatted` 与普通 Workflow 获取接口使用相同的 Skill、Workflow 和 actor 校验，但响应体只包含转换后的 JSON object。当前转换函数为深拷贝透传，因此响应等于普通接口的 `document` 字段；后续自定义格式只修改该转换函数，不改变接口路径。

`GET /api/skills/{skill_id}/workflow/executor` 是面向受信网络内执行器的无认证只读投影。它实时读取当前保存的 Workflow，不执行领域校验，不缓存或持久化结果；Log/Config CollectionCall 被静默过滤且不占用执行器 ID，表达式和 CLI binding 对其输出的引用保持原样。字段映射、Binding 路径、错误码、安全假设及不支持字段见[执行器 Workflow 转换接口](executor-workflow-api.md)。该接口不得与原样透传的 `workflow/formatted` 混用。

`GET /api/workflow-log-schema` 是全局只读契约接口，使用标准 actor context，不绑定 Skill。接口使用严格 response model，拒绝额外字段；响应严格为：

```json
{
  "document_schema_version": 5,
  "dialect": "duckdb",
  "logs_table": "logs",
  "params_table": "params",
  "columns": [
    { "name": "event_time", "duckdb_type": "TIMESTAMP", "nullable": true, "title": "时间", "description": "日志事件时间（无时区）" },
    { "name": "device", "duckdb_type": "VARCHAR", "nullable": true, "title": "设备", "description": "日志来源设备" },
    { "name": "module", "duckdb_type": "VARCHAR", "nullable": true, "title": "模块", "description": "产生日志的模块" },
    { "name": "severity", "duckdb_type": "VARCHAR", "nullable": true, "title": "严重等级", "description": "日志严重等级" },
    { "name": "brief", "duckdb_type": "VARCHAR", "nullable": true, "title": "简述", "description": "日志摘要" },
    { "name": "body", "duckdb_type": "VARCHAR", "nullable": true, "title": "日志体", "description": "原始日志正文" }
  ]
}
```

日志 SQL 的完整字段、`params` 引用、查询输出契约和静态校验见 [Workflow 日志 SQL 聚合](workflow-log-sql-aggregation.md)。SkillHub 不执行 SQL，不保存 DataFrame，也不提供日志上传或 SQL 运行接口。

Workflow 单步调试接口均要求 `skill.edit`。启动请求在同一数据库快照内读取当前保存的 revision，并复用 executor GET 的同一纯投影入口；发送给外部执行器的 `workflow_data` 与该 revision 的 `ExecutorWorkflow` 深度相等，不包含 revision、digest、调试字段或内部 ID 映射。当前 Step 包含 Log/Config 时启动返回稳定的 `workflow_debug.unsupported_collection_type`，但案例和历史接口仍可使用。调试例、状态机、暂停恢复、分页和环境配置见[Workflow 单步调试](workflow-step-debug-api.md)。

Workflow 校验问题统一包含 `id`、`code`、`severity`、`message` 和 `selection`。`selection` 使用 `type` 定位编辑区域，并按需携带 `id`、`revision`、`section`、`itemId` 和 `field`；采集调用相关问题必须提供 `section: "collections"`、调用 `itemId`，字段级问题还必须提供 `field`。

问题 `id` 的稳定身份依次由 `code`、`selection.type`、`selection.id`、`selection.revision`、`selection.section`、`selection.itemId`、`selection.field` 组成。各部分按 RFC 3986 编码后以 `/` 连接，并追加同身份问题从 `0` 开始的局部序号。前后端必须生成相同 ID；新增其他身份的问题不得改变已有 ID。

必填 ID 或 key 为空时使用对应的 `MISSING_*` code，非空值重复时使用 `DUPLICATE_*` code。缺失码包括 `MISSING_NODE_ID`、`MISSING_INPUT_ID`、`MISSING_INPUT_KEY`、`MISSING_ROLE_ID`、`MISSING_ROLE_KEY`、`MISSING_CALL_ID`、`MISSING_TRANSITION_ID`、`MISSING_COLLECTION_INPUT_ID`、`MISSING_COLLECTION_INPUT_KEY`、`MISSING_COLLECTION_OUTPUT_ID`、`MISSING_COLLECTION_OUTPUT_KEY` 和 `MISSING_COLLECTION_SAMPLE_ID`。Collection reference 与可选 call key 只检查重复。

`POST /api/workflows`：

```json
{
  "slug": "interface-check",
  "owner_ref": "network-team",
  "description": "检查网络接口状态。",
  "tags": [{ "group_id": "domain", "value": "network" }]
}
```

创建后 Workflow 与 Skill 永久绑定。初始 `SKILL.md` 只有安全 YAML frontmatter，初始版本号固定为 `0.0.1`。

`PUT /api/skills/{skill_id}/workflow`：

```json
{
  "document": { "documentType": "workflow_bundle", "workflow": {}, "collectionSnapshots": [] },
  "collection_changes": [
    { "operation": "create", "definition": {} },
    { "operation": "revise", "definition": {} },
    { "operation": "fork", "definition": {} }
  ]
}
```

Workflow 保存和导入统一写入 `document_schema_version = 5`。Parameter 与 Collection Output 使用递归 JSON Schema 描述 object、array 和标量；历史 v3/v4 文档在读取时按兼容迁移和 v5 严格联合读取，下一次正常保存才写 v5。

- 服务端执行最后写入者覆盖，不接收 `expected_revision`。
- 相同文档且没有 Collection 变更时不增加 revision。
- 结构错误拒绝保存；领域 `error/warning` 可保存为草稿。
- CollectionChanges 与 Workflow 在同一事务提交，服务端返回规范化文档和正式 revision。
- 步骤内新建采集仍使用 `operation: "create"`，不存在独立即时入库接口。
- 参数 Key/名称、Collection 输出 Key、Collection 名称或单行 CLI 命令缺失属于领域 `error`，允许保存但阻止同步。Collection 调用 Key 可为空；为空时输出字段直接暴露，若与全局输入或其他直接暴露输出冲突则阻止同步。多次采集必须填写当前 Step 内合法 Python 标识符形式的调用 Key；不同 Step 可以复用同名 Key。
- 日志 Collection 的输入/输出只允许 `string`、`integer`、`number`、`boolean`；每个输出必须且只能归属一条查询，SQL 顶层 alias 必须与输出 Key 一致。日志调用固定 `sampleCount = 1` 且不支持 `deviceRoleId`。SQL AST 错误属于领域 `error`，允许保存草稿但阻止同步。
- 配置匹配 Collection 使用 `config.commands` 命令树和单行尖括号模式；命令/捕获名、捕获 Schema、同级重复及跨调用根命名冲突属于领域 `error`。配置调用固定 `sampleCount = 1`，可按设备角色隔离上下文；结果通过 `config` 表达式根访问。当前 executor 投影对 Config 返回 `executor_workflow.unsupported_collection_type`。

`GET /api/skills/{skill_id}/workflow/export` 返回严格的 `WorkflowImportBundle`。接口读取当前服务端已保存 revision，按 Call 首次出现顺序导出实际引用的 Collection 精确版本，并使用确定性的 `collection_1`、`collection_2` 等 `localId` 重写引用。响应不包含 Workflow/Collection 持久化 ID、revision、`forkedFrom`、权限或版本历史，也不包含未引用的全局 Catalog 定义。该文件是跨实例可移植快照，不是数据库备份。

`POST /api/skills/{skill_id}/workflow/import` 直接接收 `documentType: "workflow_import_bundle"`。导入 Workflow 不包含持久化 ID/revision；Collection 使用请求内 `localId`，Call 使用 `definitionLocalId`。服务端为每个导入定义生成新 ID 和 revision 1，并返回 `import_result.collection_mappings`。接口要求 `skill.edit` 且不幂等，重复提交会创建新的 Workflow revision 和 Collection；结构或引用失败时整个事务回滚。

`GET /api/workflow-skill-generators` 返回固定内置目录：

```json
{
  "default_generator_id": "builtin.three-file",
  "generators": [
    {
      "id": "builtin.three-file",
      "version": "2.0.0",
      "label": "固定三文件",
      "default": true,
      "options_schema": { "type": "object", "properties": {}, "additionalProperties": false }
    }
  ]
}
```

完整目录还包含 `builtin.single-file@workflow-skill-v5.1`、`builtin.three-file@3.1.0` 和 `builtin.node-split@3.1.0`。v5.1 Generator 会在日志 Collection 中展示 SQL、输出映射和样例名称，并为多次采集输出展示索引路径，不输出样例原文；内置 Generator 只接受空 options，不支持运行时模板、用户模板或 LLM 生成。

`GET /api/workflow-expression-contract` 返回条件表达式允许使用的根变量、函数、方法与类型代数。`environment.outputs` 的命名采集使用 `{sampleCount, fields}` 描述采样结果；无 `callKey` 的直接输出使用 `{sampleCount, schema}` 表示 `outputs.<outputKey>` 本身的值类型；旧字段 map 按单次采集兼容。

`POST /api/workflow-expression-validations` 和批量 `POST /api/workflow-expression-validations/batch` 只执行 AST 与类型检查并返回定位诊断；HTTP 接口不执行 expression evaluator。采样下标问题作为 Workflow warning。

`POST /api/skills/{skill_id}/workflow/sync-preview`：

```json
{
  "expected_workflow_revision": 7,
  "generator_id": "builtin.three-file",
  "generator_options": {}
}
```

响应包含规范化 `generator`、`generator_options`、`files`、`bundle_digest`、与当前 SkillVersion 的 `diff`、`warnings`、`action` 和 `preview_digest`。`action.mode` 为 `create`、`reactivate` 或 `already_current`。预览只执行权限校验、读取和纯计算，不创建 Artifact、SkillVersion、WorkflowSync 或审计事件。

`POST /api/skills/{skill_id}/workflow/sync`：

```json
{
  "version": "0.0.2",
  "display_name": "Workflow v2",
  "change_summary": "从 Workflow 同步接口排查流程。",
  "expected_workflow_revision": 7,
  "generator_id": "builtin.three-file",
  "generator_version": "1.0.0",
  "generator_options": {},
  "preview_digest": "<64 位 sha256>"
}
```

- 存在校验 `error` 时返回业务错误；`warning` 不阻止同步。
- 服务端正式写入前重新生成 Bundle；Workflow revision、文档 digest、Generator version、options 或输出 digest 与预览不一致时返回 `409`，且不写入任何事实。
- `preview_digest` 覆盖 Workflow ID/revision/document digest、Generator ID/version/options 和 Bundle digest。
- 唯一生成身份为 `workflow_id + workflow_revision + generator_id + generator_version + generator_options_digest`；同一 revision 可由三个 Generator 分别生成 SkillVersion。
- 已生成版本不是当前版本时返回 `mode: "reactivated"`；已经是当前版本时返回 `mode: "already_current"`。
- 精确重复同步沿用原版本，忽略请求中的新版本元数据；新身份成功生成时返回 `mode: "created"`。
- SkillVersion 的 `workflow_sync` 和同步审计 payload 均返回完整 Generator 证据与 `preview_digest`。

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
