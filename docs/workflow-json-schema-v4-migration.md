# Workflow JSON Schema v4 迁移手册

本文档用于将已运行的 SkillHub 环境从 Alembic revision `0002_skill_identity_global_admin` 升级到 `0003_workflow_json_schema_v4`。本次升级会重写当前 Workflow JSONB，并为仍在使用的 Collection revision 创建 v4 副本，因此必须按停写、备份、单次迁移、验证、恢复流量的顺序执行。

## 1. 适用范围与限制

- 目标数据库必须是 PostgreSQL。
- 推荐的迁移前 revision 是 `0002_skill_identity_global_admin`。
- API、Worker 和 Web 不支持新旧版本混跑。
- `0003` 不支持 downgrade。回退必须同时恢复旧版应用和迁移前数据库备份。
- 未纳入 Alembic 的数据库不得直接 `stamp head`。如果 JSONB 仍是 Workflow v3，直接 stamp 会跳过数据迁移。
- 本次只升级 Schema 定义、编辑、校验和绑定数据，不执行 Workflow 调度、CLI 提取或运行时回显迁移。

## 2. 数据变化

迁移会执行以下操作：

- 所有 Workflow 的 `document_schema_version` 更新为 `4`。
- 每个 Workflow revision 增加 `1`，重算 `document_digest`，并记录迁移 actor `system:migration:workflow-json-schema-v4`。
- Workflow 和 Collection 的输入、输出从 `dataType`、`name`、`description` 转为递归 `schema`。
- 旧输入的 `required` 原样保留；旧输出统一迁移为 optional。
- 当前最新以及被 Workflow 引用的旧 Collection revision 会生成新的 v4 revision。
- Collection 历史 revision 保持不变；Catalog 的 `latest_revision` 和 Workflow 引用更新到 v4 revision。
- Workflow 的 `collectionSnapshots` 根据更新后的引用重建。
- WorkflowSync、SkillVersion 和历史 source artifact 保持不变。由于 Workflow revision 增加，已同步 Workflow 会显示为 `workflow_changed`，需要重新同步。
- 旧 `array` 和 `object` 会转为可继续使用的宽松兼容 Schema，并在编辑器中显示兼容 warning。
- 固定值和条件表达式保留原文。

迁移在 Alembic 事务内执行。任何一项失败时，当前迁移事务应整体回滚。

## 3. 迁移前检查

记录发布 commit，并确认后端、前端和 migration 来自同一个 commit。

检查数据库 revision：

```sql
SELECT version_num FROM alembic_version;
```

预期结果：

```text
0002_skill_identity_global_admin
```

如果数据库是 `0001_initial_schema`，必须先在生产副本上演练连续升级。如果 revision 为空、未知或存在多 head，停止部署并先完成数据库基线审计。

记录迁移前数据基线：

```sql
SELECT document_schema_version, count(*)
FROM workflows
GROUP BY document_schema_version
ORDER BY document_schema_version;

SELECT document_schema_version, count(*)
FROM workflow_collection_revisions
GROUP BY document_schema_version
ORDER BY document_schema_version;

SELECT id, revision, document_schema_version, document_digest
FROM workflows
ORDER BY id;

SELECT id, latest_revision
FROM workflow_collection_definitions
ORDER BY id;
```

建议将后两项导出为 CSV。迁移后每个 Workflow revision 应只增加 `1`。

在生产数据库副本上至少完成一次完整演练，并记录执行时间。迁移会读取和更新全部 Workflow，数据量较大时应据此安排维护窗口。

## 4. 停写与备份

1. 从负载均衡摘除旧 API。
2. 停止所有 API 和 Worker。
3. 将 Web 切换到维护页，避免用户继续编辑 Workflow。
4. 确认没有运行中的发布、测评或保存请求。
5. 创建 PostgreSQL custom-format 备份。

```bash
pg_dump \
  --format=custom \
  --file="skillhub-before-workflow-v4-$(date +%Y%m%d%H%M%S).dump" \
  "$SKILLHUB_DATABASE_URL"
```

验证备份目录可读取：

```bash
pg_restore --list skillhub-before-workflow-v4-*.dump >/dev/null
```

生产发布前应至少演练一次恢复：

```bash
createdb skillhub_restore_test
pg_restore --dbname=skillhub_restore_test skillhub-before-workflow-v4-*.dump
```

## 5. 执行迁移

从待发布 commit 或同版本容器镜像执行一次迁移任务。禁止每个 API 或 Worker 副本自行执行。

```bash
cd /opt/skillhub/repo/apps/backend
uv sync --frozen --no-dev

export SKILLHUB_DATABASE_URL='postgresql+psycopg://skillhub:***@db:5432/skillhub'
uv run python -m skillhub.models.schema.cli upgrade
```

迁移成功后立即执行结构检查：

```bash
uv run python -m skillhub.models.schema.cli check
uv run alembic check
```

## 6. 数据验证

确认 revision：

```sql
SELECT version_num FROM alembic_version;
```

预期结果是 `0003_workflow_json_schema_v4`。

确认所有当前 Workflow 已是 v4：

```sql
SELECT count(*) AS invalid_workflows
FROM workflows
WHERE document_schema_version <> 4;
```

预期为 `0`。

确认 Collection 最新 revision 已是 v4。历史 v3 revision 仍然存在是正常结果：

```sql
SELECT count(*) AS invalid_latest_collections
FROM workflow_collection_definitions d
JOIN workflow_collection_revisions r
  ON r.definition_id = d.id
 AND r.revision = d.latest_revision
WHERE r.document_schema_version <> 4;
```

预期为 `0`。

确认 Workflow 引用存在且指向 v4 Collection：

```sql
WITH refs AS (
  SELECT
    w.id AS workflow_id,
    call->'definition'->>'id' AS definition_id,
    (call->'definition'->>'revision')::integer AS revision
  FROM workflows w
  CROSS JOIN LATERAL
    jsonb_array_elements(w.document->'workflow'->'nodes') AS node
  CROSS JOIN LATERAL
    jsonb_array_elements(COALESCE(node->'collectionCalls', '[]'::jsonb)) AS call
)
SELECT refs.*
FROM refs
LEFT JOIN workflow_collection_revisions r
  ON r.definition_id = refs.definition_id
 AND r.revision = refs.revision
WHERE r.definition_id IS NULL
   OR r.document_schema_version <> 4;
```

预期没有记录。最后对照迁移前 CSV，确认 Workflow revision、Collection latest revision 和总记录数符合预期。

## 7. 恢复服务与冒烟测试

1. 启动一个新版 API 实例。
2. 检查 `/health`、`/api/skills` 和表达式契约接口。
3. 恢复全部新版 API。
4. 启动新版 Worker，并确认 Worker ID 唯一且在线。
5. 部署同一 commit 构建的前端。
6. 完成浏览器冒烟后恢复流量。

```bash
curl -f https://skillhub.example.com/health
curl -f https://skillhub.example.com/api/skills
curl -f https://skillhub.example.com/api/workflow-expression-contract
```

浏览器至少验证：历史 Workflow 可读取、标量字段显示正确、旧对象显示兼容 warning、对象数组可编辑、复杂固定值可校验、前序输出绑定正确，以及已同步 Workflow 可重新同步。

## 8. 失败与回滚

- 迁移命令失败：保持服务停止，确认事务已回滚，修复数据问题后重新执行。
- 迁移成功但新版应用无法启动：停止所有新版服务，恢复迁移前备份，并部署迁移前 commit。禁止只回滚应用。
- 恢复流量后发现问题：优先向前修复。恢复旧备份会丢失迁移后产生的数据。

`0003` 的 `downgrade()` 会直接拒绝执行，因此备份和恢复演练是本次部署的强制步骤。
